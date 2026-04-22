import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


logger = logging.getLogger(__name__)


ORDER_STATUS_LABELS = {
    "pending": "Chờ xử lý",
    "shipping": "Đang giao hàng",
    "completed": "Hoàn thành",
    "cancelled": "Đã hủy",
}

RETURN_REQUEST_STATUS_LABELS = {
    "processing": "Đang xử lý",
    "approved_refund": "Chấp nhận hoàn tiền",
    "rejected_refund": "Từ chối hoàn tiền",
}


def build_absolute_url(view_name, *, request=None, args=None):
    url = reverse(view_name, args=args or [])
    if request is not None:
        return request.build_absolute_uri(url)

    site_base_url = (getattr(settings, "SITE_BASE_URL", "") or "").strip().rstrip("/")
    if site_base_url:
        return f"{site_base_url}{url}"
    return url


def get_order_recipient_email(order):
    user = getattr(order, "user", None)
    if user and getattr(user, "email", ""):
        return user.email.strip()
    return ""


def get_return_request_recipient_email(return_request):
    order = getattr(return_request, "order", None)
    if order is not None:
        recipient_email = get_order_recipient_email(order)
        if recipient_email:
            return recipient_email

    return (getattr(return_request, "contact_email", "") or "").strip()


def get_order_status_label(status):
    return ORDER_STATUS_LABELS.get(status, status or "Không xác định")


def get_return_request_status_label(status):
    return RETURN_REQUEST_STATUS_LABELS.get(status, status or "Không xác định")


def build_order_email_context(order, request=None):
    order_items = list(order.items.select_related("medicine").all())
    return {
        "site_name": getattr(settings, "SITE_NAME", "GIS Pharma"),
        "support_email": getattr(settings, "SITE_SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "order": order,
        "order_items": order_items,
        "order_history_url": build_absolute_url("order_history", request=request),
        "order_detail_url": build_absolute_url("order_history_detail", request=request, args=[order.pk]),
        "invoice_url": build_absolute_url("order_invoice_view", request=request, args=[order.pk]),
        "recipient_name": order.full_name or "Quý khách",
    }


def build_order_status_email_context(order, previous_status, request=None):
    context = build_order_email_context(order, request=request)
    context.update(
        {
            "previous_status": previous_status,
            "previous_status_label": get_order_status_label(previous_status),
            "current_status": order.status,
            "current_status_label": get_order_status_label(order.status),
            "payment_status_label": getattr(order, "get_payment_status_display", lambda: "")(),
        }
    )
    return context


def build_return_request_email_context(return_request, previous_status, request=None):
    order = return_request.order
    return {
        "site_name": getattr(settings, "SITE_NAME", "GIS Pharma"),
        "support_email": getattr(settings, "SITE_SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "order": order,
        "return_request": return_request,
        "recipient_name": order.full_name or "Quý khách",
        "order_detail_url": build_absolute_url("order_history_detail", request=request, args=[order.pk]),
        "order_history_url": build_absolute_url("order_history", request=request),
        "previous_status": previous_status,
        "previous_status_label": get_return_request_status_label(previous_status),
        "current_status": return_request.status,
        "current_status_label": get_return_request_status_label(return_request.status),
        "order_status_label": get_order_status_label(order.status),
    }


def build_account_recovery_otp_context(*, user, challenge, otp_code, request=None):
    is_username_recovery = challenge.purpose == "username_recovery"
    verify_url = build_absolute_url(
        "account_recovery_verify",
        request=request,
        args=[challenge.public_token],
    )
    return {
        "site_name": getattr(settings, "SITE_NAME", "GIS Pharma"),
        "support_email": getattr(settings, "SITE_SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "user": user,
        "challenge": challenge,
        "otp_code": otp_code,
        "verify_url": verify_url,
        "is_username_recovery": is_username_recovery,
        "expires_at": challenge.expires_at,
        "otp_valid_minutes": max(int((challenge.expires_at - challenge.created_at).total_seconds() // 60), 1),
        "username_snapshot": challenge.username_snapshot or user.get_username(),
    }


def build_registration_confirmation_context(*, user, uid, token, request=None):
    activation_url = build_absolute_url("activate_account", request=request, args=[uid, token])
    return {
        "site_name": getattr(settings, "SITE_NAME", "GIS Pharma"),
        "support_email": getattr(settings, "SITE_SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "user": user,
        "recipient_name": user.get_full_name().strip() or user.get_username(),
        "activation_url": activation_url,
    }


def send_templated_email(subject_template, body_template, html_template, context, recipients):
    recipient_list = [email for email in recipients if email]
    if not recipient_list:
        return False

    try:
        subject = render_to_string(subject_template, context).strip().replace("\n", "")
        body = render_to_string(body_template, context)
        message = EmailMultiAlternatives(
            subject=subject,
            body=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )

        if html_template:
            html_body = render_to_string(html_template, context)
            message.attach_alternative(html_body, "text/html")

        message.send(fail_silently=False)
        return True
    except Exception:
        logger.exception("Không thể gửi email đến %s", recipient_list)
        return False


def send_order_confirmation_email(order, request=None):
    recipient_email = get_order_recipient_email(order)
    context = build_order_email_context(order, request=request)
    return send_templated_email(
        "emails/order_confirmation_subject.txt",
        "emails/order_confirmation.txt",
        "emails/order_confirmation.html",
        context,
        [recipient_email],
    )


def send_order_invoice_email(order, request=None):
    recipient_email = get_order_recipient_email(order)
    context = build_order_email_context(order, request=request)
    return send_templated_email(
        "emails/order_invoice_subject.txt",
        "emails/order_invoice.txt",
        "emails/order_invoice.html",
        context,
        [recipient_email],
    )


def send_order_cancelled_email(order, request=None):
    recipient_email = get_order_recipient_email(order)
    context = build_order_email_context(order, request=request)
    return send_templated_email(
        "emails/order_cancelled_subject.txt",
        "emails/order_cancelled.txt",
        "emails/order_cancelled.html",
        context,
        [recipient_email],
    )


def send_order_status_update_email(order, previous_status, request=None):
    if previous_status == order.status:
        return False

    recipient_email = get_order_recipient_email(order)
    context = build_order_status_email_context(order, previous_status, request=request)
    return send_templated_email(
        "emails/order_status_updated_subject.txt",
        "emails/order_status_updated.txt",
        "emails/order_status_updated.html",
        context,
        [recipient_email],
    )


def send_return_request_status_update_email(return_request, previous_status, request=None):
    if previous_status == return_request.status:
        return False

    recipient_email = get_return_request_recipient_email(return_request)
    context = build_return_request_email_context(return_request, previous_status, request=request)
    return send_templated_email(
        "emails/return_request_status_updated_subject.txt",
        "emails/return_request_status_updated.txt",
        "emails/return_request_status_updated.html",
        context,
        [recipient_email],
    )


def send_account_recovery_otp_email(*, user, challenge, otp_code, request=None):
    context = build_account_recovery_otp_context(
        user=user,
        challenge=challenge,
        otp_code=otp_code,
        request=request,
    )
    return send_templated_email(
        "registration/recovery_otp_subject.txt",
        "registration/recovery_otp_email.txt",
        "registration/recovery_otp_email.html",
        context,
        [challenge.email],
    )


def send_registration_confirmation_email(*, user, uid, token, request=None):
    context = build_registration_confirmation_context(
        user=user,
        uid=uid,
        token=token,
        request=request,
    )
    return send_templated_email(
        "registration/account_activation_subject.txt",
        "registration/account_activation_email.txt",
        "registration/account_activation_email.html",
        context,
        [user.email],
    )


def build_password_changed_email_context(user, *, request=None, change_source="account"):
    account_url = build_absolute_url("account", request=request)
    source_label = "trang thông tin cá nhân" if change_source == "account" else "chức năng quên mật khẩu"
    return {
        "site_name": getattr(settings, "SITE_NAME", "GIS Pharma"),
        "support_email": getattr(settings, "SITE_SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "user": user,
        "recipient_name": user.get_full_name().strip() or user.get_username(),
        "account_url": account_url,
        "change_source": change_source,
        "change_source_label": source_label,
        "changed_at": settings.TIME_ZONE,
    }


def send_password_changed_email(user, *, request=None, change_source="account"):
    recipient_email = (getattr(user, "email", "") or "").strip()
    context = build_password_changed_email_context(user, request=request, change_source=change_source)
    return send_templated_email(
        "emails/password_changed_subject.txt",
        "emails/password_changed.txt",
        "emails/password_changed.html",
        context,
        [recipient_email],
    )
