import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.urls import reverse


logger = logging.getLogger(__name__)


def get_order_recipient_email(order):
    user = getattr(order, "user", None)
    if user and getattr(user, "email", ""):
        return user.email.strip()
    return ""


def build_order_email_context(order, request=None):
    order_items = list(order.items.select_related("medicine").all())
    order_history_url = reverse("order_history")
    if request is not None:
        order_history_url = request.build_absolute_uri(order_history_url)

    return {
        "site_name": getattr(settings, "SITE_NAME", "GIS Pharma"),
        "support_email": getattr(settings, "SITE_SUPPORT_EMAIL", settings.DEFAULT_FROM_EMAIL),
        "order": order,
        "order_items": order_items,
        "order_history_url": order_history_url,
        "recipient_name": order.full_name or "Quý khách",
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
        logger.exception("Khong the gui email den %s", recipient_list)
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
