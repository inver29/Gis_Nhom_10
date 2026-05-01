from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4
import re

from django import forms
from django.conf import settings
from django.contrib.auth.forms import PasswordChangeForm
from django.core.files.storage import default_storage
from django.contrib.auth.forms import PasswordResetForm, SetPasswordForm, UserCreationForm
from django.core.exceptions import ValidationError
from django.contrib.auth.models import User
from django.db.models import Q, Sum
from django.forms import formset_factory, inlineformset_factory
from django.forms.models import BaseInlineFormSet
from django.utils import timezone

from .models import (
    AboutBuiltinSection,
    AboutPageContent,
    AboutCustomBlock,
    AboutFeaturedBranchItem,
    AboutPageSlide,
    HomeCategorySpotlightItem,
    HomeHeroSlide,
    HomePageContent,
    HomeServiceCommitmentItem,
    Medicine,
    MEDICINE_PRODUCT_TYPE_CHOICES,
    MedicinePromotion,
    MEDICINE_SHARED_SYNC_FIELDS,
    build_medicine_catalog_key,
    MedicineReview,
    NewsArticle,
    Order,
    Pharmacy,
    PharmacyReview,
    ReturnRefundEvidence,
    ReturnRefundRequest,
    PurchaseImportBatch,
    StockExportBatch,
    StockExportItem,
    sync_medicine_catalog_metadata,
    UserProfile,
)

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover
    Image = None
    UnidentifiedImageError = OSError


class MultipleImageInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.ImageField):
    def clean(self, data, initial=None):
        single_clean = super().clean
        if isinstance(data, (list, tuple)):
            cleaned_files = []
            for item in data:
                if item:
                    cleaned_files.append(single_clean(item, initial))
            return cleaned_files
        if not data:
            return []
        return [single_clean(data, initial)]


def validate_image_like_upload(uploaded_file):
    if not uploaded_file:
        return uploaded_file

    content_type = str(getattr(uploaded_file, "content_type", "") or "").lower()
    filename = str(getattr(uploaded_file, "name", "") or "").lower()
    allowed_extensions = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp")
    allowed_content_types = {
        "image/png",
        "image/jpeg",
        "image/jpg",
        "image/gif",
        "image/webp",
        "image/bmp",
        "image/x-ms-bmp",
    }

    if not filename.endswith(allowed_extensions) or (
        content_type and content_type not in allowed_content_types
    ):
        raise ValidationError("Chỉ chấp nhận tệp ảnh PNG, JPG, JPEG, GIF, WEBP hoặc BMP.")

    if Image is None:
        raise ValidationError("Máy chủ chưa cài thư viện kiểm tra ảnh. Vui lòng liên hệ quản trị viên.")

    try:
        current_position = uploaded_file.tell()
    except Exception:
        current_position = 0

    try:
        uploaded_file.seek(0)
        image = Image.open(uploaded_file)
        image.verify()
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError):
        raise ValidationError("Tệp tải lên không phải ảnh hợp lệ.")
    finally:
        try:
            uploaded_file.seek(current_position)
        except Exception:
            try:
                uploaded_file.seek(0)
            except Exception:
                pass

    return uploaded_file


class LooseMultipleImageField(forms.FileField):
    def clean(self, data, initial=None):
        if isinstance(data, (list, tuple)):
            return [validate_image_like_upload(item) for item in data if item]
        if not data:
            return []
        return [validate_image_like_upload(data)]


class LimitedMultipleImageField(forms.FileField):
    def __init__(self, *args, max_count=3, **kwargs):
        self.max_count = max_count
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        if not data:
            return []
        files = data if isinstance(data, (list, tuple)) else [data]
        files = [item for item in files if item]
        if len(files) > self.max_count:
            raise ValidationError(f"Tối đa chỉ được tải lên {self.max_count} ảnh.")
        return [validate_image_like_upload(item) for item in files]


def build_media_url(saved_name):
    try:
        return default_storage.url(saved_name)
    except Exception:
        media_url = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
        return f"{media_url}/{saved_name.lstrip('/')}"


def save_uploaded_gallery_files(uploaded_files, folder):
    uploaded_urls = []

    for uploaded in uploaded_files:
        if not uploaded:
            continue

        original_name = Path(getattr(uploaded, "name", "image")).name or "image"
        extension = Path(original_name).suffix or ".jpg"
        stem = Path(original_name).stem or "image"
        safe_stem = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in stem).strip("-_") or "image"
        saved_name = default_storage.save(
            f"{folder}/{datetime.now().strftime('%Y%m%d')}/{uuid4().hex}_{safe_stem}{extension}",
            uploaded,
        )
        uploaded_urls.append(saved_name)

    return uploaded_urls


def split_gallery_storage_names(raw_text):
    return [line.strip() for line in (raw_text or "").splitlines() if line and line.strip()]


def merge_gallery_storage_names(raw_existing_text, *, data=None, files=None, folder="", append_files=None, remove_all=False):
    data = data or {}
    files = files or {}
    existing_items = split_gallery_storage_names(raw_existing_text)
    merged_items = []

    if not remove_all:
        for index, stored_name in enumerate(existing_items):
            keep_value = str(data.get(f"gallery_keep_{index}", "1") or "1").strip().lower()
            should_keep = keep_value in {"1", "true", "yes", "on"}
            if not should_keep:
                continue

            replacement = files.get(f"gallery_replace_{index}") if hasattr(files, 'get') else None
            if replacement:
                replacement_names = save_uploaded_gallery_files([replacement], folder)
                if replacement_names:
                    merged_items.extend(replacement_names)
                    continue

            merged_items.append(stored_name)

    new_files = [uploaded for uploaded in (append_files or []) if uploaded]
    if new_files:
        merged_items.extend(save_uploaded_gallery_files(new_files, folder))

    return [item for item in merged_items if item]


def normalize_vietnamese_phone(value, *, required=False):
    raw_value = str(value or "").strip()
    if not raw_value:
        return ""

    digits = re.sub(r"\D+", "", raw_value)
    if len(digits) != 10 or not digits.startswith("0"):
        raise ValidationError("Số điện thoại phải gồm đúng 10 chữ số và bắt đầu bằng số 0.")
    return digits


def get_managed_pharmacy_for_user(user):
    if not user or not getattr(user, "is_authenticated", False):
        return None
    if not user.is_staff or user.is_superuser:
        return None

    profile, _ = UserProfile.objects.get_or_create(
        user=user,
        defaults={
            "full_name": user.get_full_name() or user.username,
            "phone": "",
            "address_text": "",
        },
    )
    if profile.managed_pharmacy is not None:
        return profile.managed_pharmacy

    if Pharmacy.objects.count() == 1:
        return Pharmacy.objects.order_by("id").first()
    return None


def apply_vietnamese_error_messages(field):
    required_message = "Vui lòng nhập thông tin này."
    error_messages = getattr(field, "error_messages", {})
    if "required" not in error_messages:
        field.error_messages["required"] = required_message
    field.error_messages.setdefault("invalid_choice", "Giá trị bạn chọn không hợp lệ.")
    field.error_messages.setdefault("invalid_list", "Dữ liệu gửi lên không hợp lệ.")
    field.error_messages.setdefault("max_length", "Dữ liệu nhập vào quá dài.")
    field.error_messages.setdefault("min_length", "Dữ liệu nhập vào quá ngắn.")

    if isinstance(field, forms.EmailField):
        field.error_messages.setdefault("invalid", "Vui lòng nhập địa chỉ email hợp lệ.")
    elif isinstance(field, forms.IntegerField):
        field.error_messages.setdefault("invalid", "Vui lòng nhập số hợp lệ.")
        field.error_messages.setdefault("min_value", "Giá trị nhập vào nhỏ hơn mức cho phép.")
        field.error_messages.setdefault("max_value", "Giá trị nhập vào lớn hơn mức cho phép.")
    elif isinstance(field, forms.FloatField):
        field.error_messages.setdefault("invalid", "Vui lòng nhập giá trị số hợp lệ.")
        field.error_messages.setdefault("min_value", "Giá trị nhập vào nhỏ hơn mức cho phép.")
        field.error_messages.setdefault("max_value", "Giá trị nhập vào lớn hơn mức cho phép.")
    elif isinstance(field, forms.DateField):
        field.error_messages.setdefault("invalid", "Vui lòng nhập ngày hợp lệ.")
    elif isinstance(field, forms.TimeField):
        field.error_messages.setdefault("invalid", "Vui lòng nhập thời gian hợp lệ.")
    elif isinstance(field, forms.FileField):
        field.error_messages.setdefault("invalid", "Tệp tải lên không hợp lệ.")
        field.error_messages.setdefault("missing", "Không tìm thấy tệp cần tải lên.")
        field.error_messages.setdefault("empty", "Tệp tải lên đang trống.")
    elif isinstance(field, forms.ImageField):
        field.error_messages.setdefault("invalid_image", "Tệp tải lên không phải là hình ảnh hợp lệ.")
    elif isinstance(field, forms.URLField):
        field.error_messages.setdefault("invalid", "Vui lòng nhập đường dẫn hợp lệ.")


class VietnameseValidationMixin:
    use_required_attribute = False

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            apply_vietnamese_error_messages(field)
            widget = field.widget
            if widget is None:
                continue
            widget.attrs.pop("required", None)
            widget.attrs["data-django-validation"] = "1"
            if field_name in {"phone", "contact_phone"}:
                widget.attrs.setdefault("inputmode", "numeric")
                widget.attrs.setdefault("maxlength", "10")
                widget.attrs.setdefault("pattern", "0[0-9]{9}")
                widget.attrs.setdefault("placeholder", "Nhập số điện thoại 10 số")
            if isinstance(widget, forms.Select):
                widget.attrs.setdefault("data-searchable-select", "1")
            if isinstance(widget, (forms.PasswordInput,)):
                widget.attrs.setdefault("data-password-toggle", "1")

    def clean(self):
        cleaned_data = super().clean()
        for field_name in ("phone", "contact_phone"):
            if field_name not in self.fields:
                continue
            try:
                cleaned_data[field_name] = normalize_vietnamese_phone(
                    cleaned_data.get(field_name),
                    required=self.fields[field_name].required,
                )
            except ValidationError as exc:
                self.add_error(field_name, exc)
        return cleaned_data


class PasswordReuseValidationMixin:
    password_reuse_message = "Mật khẩu mới không được trùng với mật khẩu đang dùng trước đó."

    def validate_new_password_not_reused(self, password_value):
        if password_value and getattr(self, "user", None) is not None and self.user.check_password(password_value):
            raise ValidationError(self.password_reuse_message)
        return password_value

    def clean_new_password1(self):
        password_value = self.cleaned_data.get("new_password1")
        return self.validate_new_password_not_reused(password_value)


RATING_CHOICES = [
    (5, '5 sao - Rất hài lòng'),
    (4, '4 sao - Tốt'),
    (3, '3 sao - Ổn'),
    (2, '2 sao - Chưa tốt'),
    (1, '1 sao - Cần cải thiện'),
]


class BaseReviewForm(VietnameseValidationMixin, forms.ModelForm):
    rating = forms.TypedChoiceField(
        coerce=int,
        choices=RATING_CHOICES,
        label='Số sao',
        widget=forms.RadioSelect(attrs={'class': 'review-stars-input'}),
    )

    class Meta:
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(
                attrs={
                    'class': 'form-control',
                    'rows': 4,
                    'placeholder': 'Chia sẻ cảm nhận của bạn để nhà thuốc cải thiện dịch vụ...',
                }
            ),
        }
        labels = {'comment': 'Cảm nhận'}


class MedicineReviewForm(BaseReviewForm):
    class Meta(BaseReviewForm.Meta):
        model = MedicineReview


class PharmacyReviewForm(BaseReviewForm):
    class Meta(BaseReviewForm.Meta):
        model = PharmacyReview


class CheckoutForm(VietnameseValidationMixin, forms.ModelForm):
    prescription_proof_image = LimitedMultipleImageField(
        label="Ảnh đơn thuốc (tối đa 3 ảnh)",
        required=False,
        max_count=3,
        widget=MultipleImageInput(attrs={"class": "form-control-file", "accept": "image/*", "multiple": True}),
    )
    prescription_note = forms.CharField(
        label="Ghi chú đơn thuốc",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 2,
                "placeholder": "Ghi chú thêm cho dược sĩ nếu thuốc trong giỏ cần kê đơn",
            }
        ),
    )
    payment_method = forms.ChoiceField(
        label="Phương thức thanh toán",
        choices=Order.PAYMENT_METHOD_CHOICES,
        initial=Order.PAYMENT_COD,
        required=False,
        widget=forms.RadioSelect,
    )
    invoice_requested = forms.BooleanField(
        label="Xuất hóa đơn cho đơn hàng này",
        required=False,
        initial=False,
    )

    class Meta:
        model = Order
        fields = ["full_name", "phone", "address_text", "note", "prescription_note"]
        widgets = {
            "full_name": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Họ và tên người nhận"}
            ),
            "phone": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Số điện thoại liên hệ"}
            ),
            "address_text": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "Số nhà, tên đường..."}
            ),
            "note": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Ghi chú cho đơn hàng (nếu có)",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_method"].widget.attrs.update({"class": "checkout-payment-radio"})
        self.fields["invoice_requested"].widget.attrs.update({"class": "checkout-invoice-checkbox"})


class PaymentProofUploadForm(VietnameseValidationMixin, forms.ModelForm):
    payment_proof_image = forms.ImageField(
        label="Ảnh chứng từ thanh toán",
        required=False,
        widget=forms.FileInput(attrs={"class": "form-control-file", "accept": "image/*"}),
    )

    class Meta:
        model = Order
        fields = ["payment_proof_image", "payment_note"]
        widgets = {
            "payment_note": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Ghi chú nội dung chuyển khoản, số giao dịch hoặc thời gian thanh toán",
                }
            ),
        }
        labels = {
            "payment_note": "Ghi chú thanh toán",
        }

    def clean_payment_proof_image(self):
        payment_proof_image = self.cleaned_data.get("payment_proof_image")
        if not payment_proof_image:
            return payment_proof_image
        return validate_image_like_upload(payment_proof_image)

    def clean(self):
        cleaned_data = super().clean()
        payment_proof_image = cleaned_data.get("payment_proof_image")
        existing_image = getattr(self.instance, "payment_proof_image", None)
        if not payment_proof_image and not existing_image:
            self.add_error("payment_proof_image", "Vui lòng tải lên ảnh chứng từ thanh toán.")
        return cleaned_data




class ReturnRefundRequestForm(VietnameseValidationMixin, forms.ModelForm):
    bill_image = forms.FileField(
        required=False,
        label="Ảnh bill thanh toán / hóa đơn",
        widget=forms.FileInput(attrs={"class": "form-control-file", "accept": "image/*"}),
    )
    proof_images = LooseMultipleImageField(
        required=False,
        label="Ảnh chứng minh bổ sung",
        widget=MultipleImageInput(attrs={"class": "form-control-file", "accept": "image/*", "multiple": True}),
    )

    class Meta:
        model = ReturnRefundRequest
        fields = [
            "reason",
            "bank_account_number",
            "momo_account_number",
            "contact_email",
            "contact_phone",
            "bill_image",
        ]
        widgets = {
            "reason": forms.Textarea(attrs={"class": "form-control", "rows": 5, "placeholder": "Mô tả rõ lý do trả hàng / hoàn tiền..."}),
            "bank_account_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nhập số tài khoản ngân hàng (nếu có)"}),
            "momo_account_number": forms.TextInput(attrs={"class": "form-control", "placeholder": "Nhập số tài khoản MoMo (nếu có)"}),
            "contact_email": forms.EmailInput(attrs={"class": "form-control", "placeholder": "Email liên hệ"}),
            "contact_phone": forms.TextInput(attrs={"class": "form-control", "placeholder": "Số điện thoại liên hệ"}),
            "bill_image": forms.FileInput(attrs={"class": "form-control-file", "accept": "image/*"}),
        }
        labels = {
            "reason": "Lý do trả hàng / hoàn tiền",
            "bank_account_number": "Số tài khoản ngân hàng",
            "momo_account_number": "Số tài khoản MoMo",
            "contact_email": "Email liên hệ",
            "contact_phone": "Số điện thoại liên hệ",
            "bill_image": "Ảnh bill thanh toán / hóa đơn",
        }

    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop("order", None)
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.contact_phone and not self.initial.get("contact_phone"):
            self.fields["contact_phone"].initial = self.instance.contact_phone

    def clean_bill_image(self):
        bill_image = self.cleaned_data.get("bill_image")
        if not bill_image:
            return bill_image
        return validate_image_like_upload(bill_image)

    def clean(self):
        cleaned_data = super().clean()
        bank_account = (cleaned_data.get("bank_account_number") or "").strip()
        momo_account = (cleaned_data.get("momo_account_number") or "").strip()
        if not bank_account and not momo_account:
            raise forms.ValidationError("Vui lòng nhập ít nhất một thông tin nhận tiền hoàn: tài khoản ngân hàng hoặc tài khoản MoMo.")

        bill_image = cleaned_data.get("bill_image") or getattr(self.instance, "bill_image", None)
        if not bill_image:
            self.add_error("bill_image", "Vui lòng tải lên ảnh bill thanh toán hoặc hóa đơn.")

        proof_images = cleaned_data.get("proof_images") or []
        current_count = 0
        if self.instance and self.instance.pk:
            for evidence in self.instance.evidences.all():
                keep_value = str(self.data.get(f"evidence_keep_{evidence.pk}", "1") or "1").strip().lower()
                if keep_value in {"1", "true", "yes", "on"}:
                    current_count += 1
        if current_count + len(proof_images) > 10:
            raise forms.ValidationError("Tối đa chỉ được lưu 10 ảnh chứng minh cho mỗi yêu cầu.")

        return cleaned_data


class ReturnRefundRequestAdminUpdateForm(VietnameseValidationMixin, forms.ModelForm):
    class Meta:
        model = ReturnRefundRequest
        fields = ["status", "admin_note"]
        widgets = {
            "status": forms.Select(),
            "admin_note": forms.Textarea(attrs={"rows": 4, "placeholder": "Ghi chú xử lý nội bộ..."}),
        }
        labels = {
            "status": "Trạng thái xử lý",
            "admin_note": "Ghi chú nội bộ",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["status"].choices = [
            (ReturnRefundRequest.STATUS_PROCESSING, "Đang xử lý"),
            (ReturnRefundRequest.STATUS_APPROVED, "Chấp nhận hoàn tiền"),
            (ReturnRefundRequest.STATUS_REJECTED, "Từ chối hoàn tiền"),
        ]
        for field in self.fields.values():
            old_class = field.widget.attrs.get("class", "").strip()
            field.widget.attrs["class"] = f"{old_class} form-control".strip()

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get("status")
        if new_status not in {choice[0] for choice in ReturnRefundRequest.STATUS_CHOICES}:
            raise forms.ValidationError("Trạng thái xử lý không hợp lệ.")
        return cleaned_data



class PurchaseImportExcelForm(VietnameseValidationMixin, forms.Form):
    ALL_BRANCHES_VALUE = "__all__"

    pharmacy = forms.ChoiceField(
        label="Chi nhánh nhập hàng",
        choices=(),
        widget=forms.Select(attrs={"class": "form-control"}),
    )
    invoice_code = forms.CharField(
        required=False,
        label="Mã hóa đơn nhập",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Ví dụ: PN240407-01"}),
    )
    excel_file = forms.FileField(
        label="File Excel nhập hàng",
        widget=forms.FileInput(attrs={"class": "form-control-file", "accept": ".xlsx,.xls"}),
    )
    note = forms.CharField(
        required=False,
        label="Ghi chú",
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Ghi chú thêm cho phiếu nhập hàng..."}),
    )

    def __init__(self, *args, **kwargs):
        self.admin_user = kwargs.pop("admin_user", None)
        super().__init__(*args, **kwargs)
        self.staff_managed_pharmacy = get_managed_pharmacy_for_user(self.admin_user)
        pharmacy_queryset = Pharmacy.objects.order_by("name")

        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if self.staff_managed_pharmacy:
                self.fields["pharmacy"].choices = [(str(self.staff_managed_pharmacy.pk), self.staff_managed_pharmacy.name)]
                self.fields["pharmacy"].initial = str(self.staff_managed_pharmacy.pk)
                self.fields["pharmacy"].help_text = f"Bạn chỉ được nhập hàng cho chi nhánh {self.staff_managed_pharmacy.name}."
            else:
                self.fields["pharmacy"].choices = []
                self.fields["pharmacy"].help_text = "Tài khoản nhân viên chưa được gán chi nhánh quản lý."
        else:
            choices = [(str(pharmacy.pk), pharmacy.name) for pharmacy in pharmacy_queryset]
            if len(choices) > 1:
                choices = [(self.ALL_BRANCHES_VALUE, "Toàn bộ chi nhánh")] + choices
            self.fields["pharmacy"].choices = choices
            self.fields["pharmacy"].help_text = "Có thể nhập cho một chi nhánh cụ thể hoặc áp dụng cùng một file cho toàn bộ chi nhánh."

    def clean_pharmacy(self):
        pharmacy_value = (self.cleaned_data.get("pharmacy") or "").strip()
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if not self.staff_managed_pharmacy:
                raise forms.ValidationError("Tài khoản nhân viên chưa được cấp chi nhánh quản lý.")
            return str(self.staff_managed_pharmacy.pk)

        if pharmacy_value == self.ALL_BRANCHES_VALUE:
            if not Pharmacy.objects.exists():
                raise forms.ValidationError("Hiện chưa có chi nhánh nào để nhập hàng.")
            return pharmacy_value

        if not pharmacy_value.isdigit() or not Pharmacy.objects.filter(pk=int(pharmacy_value)).exists():
            raise forms.ValidationError("Chi nhánh nhập hàng không hợp lệ.")
        return pharmacy_value

    def get_target_pharmacies(self):
        pharmacy_value = (self.cleaned_data.get("pharmacy") or "").strip()
        if pharmacy_value == self.ALL_BRANCHES_VALUE:
            return list(Pharmacy.objects.order_by("name"))
        if pharmacy_value.isdigit():
            return list(Pharmacy.objects.filter(pk=int(pharmacy_value)).order_by("name"))
        return []

    def is_all_branches_selected(self):
        return (self.cleaned_data.get("pharmacy") or "").strip() == self.ALL_BRANCHES_VALUE

    def get_selected_scope_label(self):
        if self.is_all_branches_selected():
            return "Toàn bộ chi nhánh"
        target_pharmacies = self.get_target_pharmacies()
        return target_pharmacies[0].name if target_pharmacies else "Chưa chọn chi nhánh"

    def clean_excel_file(self):
        uploaded = self.cleaned_data.get("excel_file")
        if not uploaded:
            return uploaded
        filename = (getattr(uploaded, "name", "") or "").lower()
        if not filename.endswith((".xlsx", ".xlsm", ".xltx", ".xltm")):
            raise forms.ValidationError("Hệ thống hiện hỗ trợ file Excel định dạng .xlsx.")
        return uploaded


class StockExportBatchForm(VietnameseValidationMixin, forms.ModelForm):
    class Meta:
        model = StockExportBatch
        fields = ["pharmacy", "export_scope", "export_code", "destination_name", "note"]
        widgets = {
            "pharmacy": forms.Select(),
            "export_scope": forms.Select(),
            "export_code": forms.TextInput(attrs={"placeholder": "Ví dụ: PX240414-01"}),
            "destination_name": forms.TextInput(attrs={"placeholder": "Ví dụ: Xuất nội bộ / Chuyển kho / Hủy hàng"}),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "Ghi chú thêm cho phiếu xuất kho..."}),
        }
        labels = {
            "pharmacy": "Chi nhánh xuất kho",
            "export_scope": "Loại phiếu xuất",
            "export_code": "Mã phiếu xuất",
            "destination_name": "Nơi nhận / mục đích xuất",
            "note": "Ghi chú",
        }

    def __init__(self, *args, **kwargs):
        self.admin_user = kwargs.pop("admin_user", None)
        super().__init__(*args, **kwargs)
        self.staff_managed_pharmacy = get_managed_pharmacy_for_user(self.admin_user)
        self.fields["pharmacy"].queryset = Pharmacy.objects.order_by("name")
        self.fields["pharmacy"].empty_label = "Chọn chi nhánh"
        self.fields["export_scope"].help_text = (
            "Chọn đúng loại phiếu để hệ thống nạp danh sách sản phẩm phù hợp: "
            "xuất bán được, đối soát tồn vật lý hoặc xử lý hàng hết hạn."
        )
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if self.staff_managed_pharmacy:
                self.fields["pharmacy"].queryset = Pharmacy.objects.filter(pk=self.staff_managed_pharmacy.pk)
                self.fields["pharmacy"].initial = self.staff_managed_pharmacy
                self.fields["pharmacy"].empty_label = None
                self.fields["pharmacy"].help_text = f"Bạn chỉ được xuất kho cho chi nhánh {self.staff_managed_pharmacy.name}."
            else:
                self.fields["pharmacy"].queryset = Pharmacy.objects.none()
                self.fields["pharmacy"].help_text = "Tài khoản nhân viên chưa được gán chi nhánh quản lý."

    def clean_pharmacy(self):
        pharmacy = self.cleaned_data.get("pharmacy")
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if not self.staff_managed_pharmacy:
                raise forms.ValidationError("Tài khoản nhân viên chưa được cấp chi nhánh quản lý.")
            return self.staff_managed_pharmacy
        return pharmacy


class StockExportItemForm(VietnameseValidationMixin, forms.Form):
    medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.none(),
        label="Sản phẩm",
        empty_label="Chọn sản phẩm cần xuất",
        widget=forms.Select(),
    )
    quantity = forms.IntegerField(
        min_value=1,
        label="Số lượng xuất",
        widget=forms.NumberInput(attrs={"min": 1, "step": 1, "placeholder": "Nhập số lượng"}),
    )
    note = forms.CharField(
        required=False,
        label="Ghi chú dòng",
        widget=forms.TextInput(attrs={"placeholder": "Ví dụ: Hàng hủy / Chuyển kho / Dùng nội bộ"}),
    )

    def __init__(self, *args, **kwargs):
        pharmacy = kwargs.pop("pharmacy", None)
        admin_user = kwargs.pop("admin_user", None)
        allocation_mode = kwargs.pop("allocation_mode", StockExportBatch.EXPORT_SCOPE_STANDARD)
        super().__init__(*args, **kwargs)
        managed_pharmacy = get_managed_pharmacy_for_user(admin_user)
        queryset = Medicine.objects.select_related("pharmacy").order_by("name", "id")
        if pharmacy is not None:
            queryset = queryset.filter(pharmacy=pharmacy)
        elif admin_user and admin_user.is_staff and not admin_user.is_superuser:
            if managed_pharmacy:
                queryset = queryset.filter(pharmacy=managed_pharmacy)
            else:
                queryset = queryset.none()
        today = timezone.localdate()
        if allocation_mode == StockExportBatch.EXPORT_SCOPE_EXPIRED:
            queryset = queryset.filter(
                lots__remaining_quantity__gt=0,
                lots__expiry_date__isnull=False,
                lots__expiry_date__lt=today,
            ).distinct()
            self.fields["medicine"].help_text = (
                "Chỉ hiển thị sản phẩm còn tồn ở các lô đã hết hạn để lập phiếu xử lý."
            )
        else:
            queryset = queryset.filter(
                lots__remaining_quantity__gt=0,
            ).filter(
                Q(lots__expiry_date__isnull=True) | Q(lots__expiry_date__gte=today)
            ).distinct()
            self.fields["medicine"].help_text = (
                "Chỉ hiển thị sản phẩm còn tồn bán được. Hàng đã hết hạn được xử lý riêng bằng phiếu xuất xử lý."
            )
        self.fields["medicine"].queryset = queryset
        self.allocation_mode = allocation_mode

    def clean_quantity(self):
        quantity = int(self.cleaned_data.get("quantity") or 0)
        if quantity <= 0:
            raise forms.ValidationError("Số lượng xuất phải lớn hơn 0.")
        return quantity

    def clean(self):
        cleaned_data = super().clean()
        medicine = cleaned_data.get("medicine")
        quantity = cleaned_data.get("quantity")
        if medicine and quantity:
            today = timezone.localdate()
            lot_queryset = medicine.lots.filter(remaining_quantity__gt=0)
            if self.allocation_mode == StockExportBatch.EXPORT_SCOPE_EXPIRED:
                lot_queryset = lot_queryset.filter(expiry_date__isnull=False, expiry_date__lt=today)
            else:
                lot_queryset = lot_queryset.filter(Q(expiry_date__isnull=True) | Q(expiry_date__gte=today))
            available_quantity = lot_queryset.aggregate(total=Sum("remaining_quantity")).get("total") or 0
            if quantity > int(available_quantity or 0):
                if self.allocation_mode == StockExportBatch.EXPORT_SCOPE_EXPIRED:
                    self.add_error("quantity", f"Số lượng xử lý vượt quá tồn hết hạn hiện có ({available_quantity}).")
                else:
                    self.add_error("quantity", f"Số lượng xuất vượt quá tồn bán được hiện có ({available_quantity}).")
        return cleaned_data


StockExportItemFormSet = formset_factory(
    StockExportItemForm,
    extra=8,
    can_delete=True,
)


class AboutPageContentForm(VietnameseValidationMixin, forms.ModelForm):
    FIELD_GROUPS = [
        (
            "Đầu trang và nút điều hướng",
            [
                "page_title",
                "hero_kicker",
                "hero_title",
                "hero_intro",
                "hero_chip_1",
                "hero_chip_2",
                "hero_chip_3",
                "hero_primary_label",
                "hero_secondary_label",
                "visual_title",
                "visual_description",
            ],
        ),
        ("Thống kê nhanh", ["stat_pharmacy_label", "stat_medicine_label", "stat_order_label", "stat_review_label"]),
        (
            "Câu chuyện hệ thống",
            [
                "story_tag",
                "story_title",
                "story_body",
                "story_item_1_title",
                "story_item_1_body",
                "story_item_2_title",
                "story_item_2_body",
                "story_item_3_title",
                "story_item_3_body",
            ],
        ),
        (
            "Giá trị nổi bật",
            [
                "value_tag",
                "value_title",
                "value_body",
                "value_card_1_title",
                "value_card_1_body",
                "value_card_2_title",
                "value_card_2_body",
                "value_card_3_title",
                "value_card_3_body",
            ],
        ),
        (
            "Hành trình vận hành",
            [
                "journey_tag",
                "journey_title",
                "journey_body",
                "step_1_title",
                "step_1_body",
                "step_2_title",
                "step_2_body",
                "step_3_title",
                "step_3_body",
                "step_4_title",
                "step_4_body",
            ],
        ),
        (
            "Vai trò chi nhánh",
            [
                "branch_role_tag",
                "branch_role_title",
                "branch_role_body",
                "branch_role_item_1_title",
                "branch_role_item_1_body",
                "branch_role_item_2_title",
                "branch_role_item_2_body",
                "branch_role_item_3_title",
                "branch_role_item_3_body",
            ],
        ),
        (
            "Chi nhánh tiêu biểu",
            [
                "branch_showcase_tag",
                "branch_showcase_title",
                "branch_showcase_body",
                "branch_showcase_badge",
                "branch_showcase_map_note",
                "branch_empty_tag",
                "branch_empty_title",
                "branch_empty_body",
            ],
        ),
        ("Lời kêu gọi hành động", ["cta_title", "cta_body", "cta_primary_label", "cta_secondary_label"]),
    ]

    class Meta:
        model = AboutPageContent
        fields = [
            "page_title",
            "hero_kicker",
            "hero_title",
            "hero_intro",
            "hero_chip_1",
            "hero_chip_2",
            "hero_chip_3",
            "hero_primary_label",
            "hero_secondary_label",
            "visual_title",
            "visual_description",
            "stat_pharmacy_label",
            "stat_medicine_label",
            "stat_order_label",
            "stat_review_label",
            "story_tag",
            "story_title",
            "story_body",
            "story_item_1_title",
            "story_item_1_body",
            "story_item_2_title",
            "story_item_2_body",
            "story_item_3_title",
            "story_item_3_body",
            "value_tag",
            "value_title",
            "value_body",
            "value_card_1_title",
            "value_card_1_body",
            "value_card_2_title",
            "value_card_2_body",
            "value_card_3_title",
            "value_card_3_body",
            "journey_tag",
            "journey_title",
            "journey_body",
            "step_1_title",
            "step_1_body",
            "step_2_title",
            "step_2_body",
            "step_3_title",
            "step_3_body",
            "step_4_title",
            "step_4_body",
            "branch_role_tag",
            "branch_role_title",
            "branch_role_body",
            "branch_role_item_1_title",
            "branch_role_item_1_body",
            "branch_role_item_2_title",
            "branch_role_item_2_body",
            "branch_role_item_3_title",
            "branch_role_item_3_body",
            "branch_showcase_tag",
            "branch_showcase_title",
            "branch_showcase_body",
            "branch_showcase_badge",
            "branch_showcase_map_note",
            "branch_empty_tag",
            "branch_empty_title",
            "branch_empty_body",
            "cta_title",
            "cta_body",
            "cta_primary_label",
            "cta_secondary_label",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field_name, field in self.fields.items():
            if isinstance(field.widget, forms.CheckboxInput):
                field.widget.attrs["class"] = "form-check-input"
                continue
            field.widget.attrs.setdefault("class", "form-control")
            if isinstance(field.widget, forms.Textarea):
                field.widget.attrs.setdefault("rows", "4")
                field.widget.attrs["data-rich-editor"] = "1"


class HomePageContentForm(VietnameseValidationMixin, forms.ModelForm):
    FIELD_GROUPS = [
        ("Slider đầu trang", ["hero_autoplay_interval"]),
        (
            "Khối danh mục nổi bật",
            ["category_section_kicker", "category_section_title", "category_section_link_label", "category_section_link_url"],
        ),
        ("Khối cam kết dịch vụ", ["commitment_section_kicker", "commitment_section_title"]),
    ]

    class Meta:
        model = HomePageContent
        exclude = ["singleton_key", "updated_at"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["hero_autoplay_interval"].widget.attrs.setdefault("min", "1500")
        self.fields["hero_autoplay_interval"].widget.attrs.setdefault("step", "100")


class RegisterForm(VietnameseValidationMixin, forms.ModelForm):
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Tạo mật khẩu",
            }
        ),
    )
    confirm_password = forms.CharField(
        label="Nhập lại mật khẩu",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập lại mật khẩu",
            }
        ),
    )

    class Meta:
        model = User
        fields = ["username", "email", "password"]
        labels = {"username": "Tên đăng nhập", "email": "Email"}
        widgets = {
            "username": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "autocomplete": "username",
                    "placeholder": "Ví dụ: nguyenvana",
                }
            ),
            "email": forms.EmailInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "name@example.com",
                }
            ),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("password") != cleaned_data.get("confirm_password"):
            raise forms.ValidationError("Mật khẩu không khớp")
        return cleaned_data

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Email này đã được dùng để đăng ký tài khoản.")
        return email


class LoginForm(VietnameseValidationMixin, forms.Form):
    username = forms.CharField(
        label="Tên đăng nhập",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "autocomplete": "username",
                "placeholder": "Nhập tên đăng nhập",
            }
        ),
    )
    password = forms.CharField(
        label="Mật khẩu",
        widget=forms.PasswordInput(
            attrs={
                "class": "form-control",
                "autocomplete": "current-password",
                "placeholder": "Nhập mật khẩu",
            }
        ),
    )


class AccountProfileForm(VietnameseValidationMixin, forms.Form):
    full_name = forms.CharField(
        label="Họ tên",
        max_length=150,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nhập họ tên của bạn"}),
    )
    email = forms.EmailField(
        label="Email",
        required=False,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.com"}),
    )
    phone = forms.CharField(
        label="Số điện thoại",
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "Nhập số điện thoại"}),
    )
    address_text = forms.CharField(
        label="Địa chỉ mặc định",
        required=False,
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 3,
                "placeholder": "Nhập địa chỉ giao hàng mặc định",
            }
        ),
    )
    address_lat = forms.FloatField(required=False, widget=forms.HiddenInput())
    address_lng = forms.FloatField(required=False, widget=forms.HiddenInput())

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop("user")
        self.profile = kwargs.pop("profile")
        self.is_customer = kwargs.pop("is_customer", False)
        super().__init__(*args, **kwargs)

        self.fields["full_name"].initial = (
            self.profile.full_name
            or self.user.get_full_name()
            or self.user.username
        )
        self.fields["email"].initial = self.user.email
        self.fields["phone"].initial = self.profile.phone
        self.fields["address_text"].initial = self.profile.address_text
        self.fields["address_lat"].initial = self.profile.address_lat
        self.fields["address_lng"].initial = self.profile.address_lng

        if not self.is_customer:
            self.fields.pop("address_text")
            self.fields.pop("address_lat")
            self.fields.pop("address_lng")


MEDICINE_CATEGORY_CHOICES = [
    ("", "Chọn danh mục"),
    ("Giam dau - ha sot", "Giảm đau - hạ sốt"),
    ("Khang sinh", "Khang sinh"),
    ("Vitamin - khoang chat", "Vitamin - khoáng chất"),
    ("Tieu hoa", "Tiêu hóa"),
    ("Cam cum - ho", "Cảm cúm - ho"),
    ("Di ung", "Dị ứng"),
    ("Tim mach", "Tim mạch"),
    ("Da lieu", "Da liễu"),
    ("Thiet bi y te", "Thiết bị y tế"),
]

UNIT_CHOICES = [
    ("Hop", "Hộp"),
    ("Vi", "Vỉ"),
    ("Chai", "Chai"),
    ("Tuyp", "Tuýp"),
    ("Lo", "Lọ"),
    ("Goi", "Gói"),
    ("Vien", "Viên"),
]

USER_ROLE_CHOICES = [
    ("customer", "Người dùng"),
    ("staff", "Nhân viên quản trị"),
    ("superuser", "Quản trị hệ thống"),
]


class BootstrapModelForm(VietnameseValidationMixin, forms.ModelForm):
    def __init__(self, *args, **kwargs):
        self.admin_user = kwargs.pop("admin_user", None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget
            input_type = getattr(widget, "input_type", "")

            if isinstance(widget, (forms.CheckboxInput, forms.CheckboxSelectMultiple)):
                widget.attrs["class"] = "form-check-input"
                continue

            if input_type == "file":
                widget.attrs["class"] = "form-control-file"
                continue

            old_class = widget.attrs.get("class", "").strip()
            widget.attrs["class"] = f"{old_class} form-control".strip()


QUICK_PICK_CUSTOM_VALUE = "__custom__"

HOME_ICON_OPTION_PAIRS = [
    ("fas fa-capsules", "Viên nang / sản phẩm cơ bản"),
    ("fas fa-heartbeat", "Tim mạch / tiêu hóa"),
    ("fas fa-prescription-bottle-alt", "Hô hấp / dị ứng"),
    ("fas fa-syringe", "Tiêm / giảm đau"),
    ("fas fa-shield-virus", "Miễn dịch / cảm cúm"),
    ("fas fa-leaf", "Thảo dược / kháng sinh"),
    ("fas fa-certificate", "Cam kết chính hãng"),
    ("fas fa-map-marker-alt", "Bản đồ / định vị"),
    ("fas fa-shipping-fast", "Giao hàng"),
    ("fas fa-history", "Lịch sử / theo dõi"),
    ("fas fa-clinic-medical", "Nhà thuốc / chi nhánh"),
    ("fas fa-store", "Cửa hàng"),
    ("fas fa-medkit", "Túi sơ cứu"),
    ("fas fa-pills", "Viên thuốc"),
    ("fas fa-stethoscope", "Tư vấn sức khỏe"),
    ("fas fa-hand-holding-medical", "Chăm sóc y tế"),
    ("fas fa-notes-medical", "Thông tin y khoa"),
    ("fas fa-truck-medical", "Vận chuyển y tế"),
    ("fas fa-phone-alt", "Hỗ trợ điện thoại"),
    ("fas fa-user-shield", "Đảm bảo / bảo mật"),
    ("fas fa-layer-group", "Khối nội dung tổng hợp"),
]


def build_quick_select_choices(option_pairs, *, empty_label, custom_label):
    seen = set()
    choices = [("", empty_label)]
    for value, label in option_pairs:
        if not value or value in seen:
            continue
        seen.add(value)
        choices.append((value, label))
    choices.append((QUICK_PICK_CUSTOM_VALUE, custom_label))
    return choices


def resolve_quick_select_initial(current_value, choices):
    if not current_value:
        return ""
    available_values = {value for value, _ in choices if value and value != QUICK_PICK_CUSTOM_VALUE}
    return current_value if current_value in available_values else QUICK_PICK_CUSTOM_VALUE


def configure_quick_select_field(
    form,
    *,
    choice_name,
    actual_name,
    option_pairs,
    empty_label,
    custom_label,
    current_value,
):
    choices = build_quick_select_choices(option_pairs, empty_label=empty_label, custom_label=custom_label)
    form.fields[choice_name].choices = choices
    form.fields[choice_name].widget.attrs["data-searchable-select"] = "1"
    form.fields[choice_name].widget.attrs["data-quick-choice"] = actual_name
    form.fields[actual_name].widget.attrs["data-quick-custom-input"] = actual_name
    form.initial[choice_name] = resolve_quick_select_initial(current_value, choices)


def resolve_quick_select_value(cleaned_data, *, choice_name, actual_name, default_value=""):
    selected_choice = str(cleaned_data.get(choice_name) or "").strip()
    custom_value = str(cleaned_data.get(actual_name) or "").strip()
    if selected_choice and selected_choice != QUICK_PICK_CUSTOM_VALUE:
        return selected_choice
    return custom_value or default_value


class HomeHeroSlideForm(BootstrapModelForm):
    link_choice = forms.ChoiceField(required=False, label="Liên kết nhanh", choices=())

    class Meta:
        model = HomeHeroSlide
        fields = ["image", "alt_text", "link_url", "sort_order", "is_active"]
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*"}),
            "alt_text": forms.TextInput(attrs={"placeholder": "Mô tả ngắn cho ảnh slide"}),
            "link_url": forms.TextInput(attrs={"placeholder": "Ví dụ: /about/"}),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "image": "Ảnh slide",
            "alt_text": "Mô tả ảnh",
            "link_url": "Liên kết khi bấm",
            "sort_order": "Thứ tự",
            "is_active": "Hiển thị slide này",
        }

    def __init__(self, *args, **kwargs):
        link_choices = kwargs.pop("link_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["link_url"].required = False
        current_link = self.initial.get("link_url") or getattr(self.instance, "link_url", "")
        configure_quick_select_field(
            self,
            choice_name="link_choice",
            actual_name="link_url",
            option_pairs=link_choices,
            empty_label="Chọn nhanh một liên kết",
            custom_label="Tự nhập liên kết khác",
            current_value=current_link,
        )
        self.fields["link_url"].label = "Liên kết tùy chỉnh"
        self.fields["link_url"].help_text = "Chỉ cần nhập ô này khi bạn chọn mục “Tự nhập liên kết khác”."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        cleaned_data["link_url"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="link_choice",
            actual_name="link_url",
            default_value="",
        )

        has_other_data = any(
            str(cleaned_data.get(field_name) or "").strip()
            for field_name in ("alt_text", "link_url")
        ) or bool(cleaned_data.get("image"))
        has_existing_image = bool(getattr(self.instance, "image", None) or getattr(self.instance, "legacy_static_path", ""))
        if has_other_data and not (cleaned_data.get("image") or has_existing_image):
            raise forms.ValidationError("Mỗi slide cần có ảnh hiển thị hoặc ảnh dự phòng sẵn có.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("image"):
            obj.legacy_static_path = ""
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class HomeCategorySpotlightItemForm(BootstrapModelForm):
    icon_choice = forms.ChoiceField(required=False, label="Chọn icon", choices=())
    link_choice = forms.ChoiceField(required=False, label="Liên kết nhanh", choices=())

    class Meta:
        model = HomeCategorySpotlightItem
        fields = ["title", "subtitle", "icon_class", "link_url", "sort_order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ví dụ: Chăm sóc cơ bản"}),
            "subtitle": forms.TextInput(attrs={"placeholder": "Ví dụ: 10 sản phẩm"}),
            "icon_class": forms.TextInput(attrs={"placeholder": "Ví dụ: fas fa-capsules"}),
            "link_url": forms.TextInput(attrs={"placeholder": "Ví dụ: /products/?category=Cham%20soc"}),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "title": "Tiêu đề",
            "subtitle": "Dòng phụ",
            "icon_class": "Class icon",
            "link_url": "Liên kết",
            "sort_order": "Thứ tự",
            "is_active": "Hiển thị mục này",
        }

    def __init__(self, *args, **kwargs):
        icon_choices = kwargs.pop("icon_choices", HOME_ICON_OPTION_PAIRS)
        link_choices = kwargs.pop("link_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["icon_class"].required = False
        self.fields["link_url"].required = False
        current_icon = self.initial.get("icon_class") or getattr(self.instance, "icon_class", "") or "fas fa-capsules"
        current_link = self.initial.get("link_url") or getattr(self.instance, "link_url", "")
        configure_quick_select_field(
            self,
            choice_name="icon_choice",
            actual_name="icon_class",
            option_pairs=icon_choices,
            empty_label="Chọn nhanh một icon",
            custom_label="Tự nhập mã icon khác",
            current_value=current_icon,
        )
        configure_quick_select_field(
            self,
            choice_name="link_choice",
            actual_name="link_url",
            option_pairs=link_choices,
            empty_label="Chọn nhanh một liên kết",
            custom_label="Tự nhập liên kết khác",
            current_value=current_link,
        )
        self.fields["icon_class"].label = "Mã icon tùy chỉnh"
        self.fields["icon_class"].help_text = "Chỉ cần nhập khi bạn chọn mục “Tự nhập mã icon khác”."
        self.fields["link_url"].label = "Liên kết tùy chỉnh"
        self.fields["link_url"].help_text = "Chỉ cần nhập khi bạn chọn mục “Tự nhập liên kết khác”."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        cleaned_data["icon_class"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="icon_choice",
            actual_name="icon_class",
            default_value="fas fa-capsules",
        )
        cleaned_data["link_url"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="link_choice",
            actual_name="link_url",
            default_value="",
        )
        return cleaned_data


class HomeServiceCommitmentItemForm(BootstrapModelForm):
    icon_choice = forms.ChoiceField(required=False, label="Chọn icon", choices=())

    class Meta:
        model = HomeServiceCommitmentItem
        fields = ["title", "body", "icon_class", "sort_order", "is_active"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Ví dụ: Thuốc chính hãng"}),
            "body": forms.Textarea(attrs={"rows": 4, "placeholder": "Nhập mô tả hiển thị trên thẻ..."}),
            "icon_class": forms.TextInput(attrs={"placeholder": "Ví dụ: fas fa-certificate"}),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "title": "Tiêu đề",
            "body": "Nội dung",
            "icon_class": "Class icon",
            "sort_order": "Thứ tự",
            "is_active": "Hiển thị mục này",
        }

    def __init__(self, *args, **kwargs):
        icon_choices = kwargs.pop("icon_choices", HOME_ICON_OPTION_PAIRS)
        super().__init__(*args, **kwargs)
        self.fields["icon_class"].required = False
        current_icon = self.initial.get("icon_class") or getattr(self.instance, "icon_class", "") or "fas fa-certificate"
        configure_quick_select_field(
            self,
            choice_name="icon_choice",
            actual_name="icon_class",
            option_pairs=icon_choices,
            empty_label="Chọn nhanh một icon",
            custom_label="Tự nhập mã icon khác",
            current_value=current_icon,
        )
        self.fields["icon_class"].label = "Mã icon tùy chỉnh"
        self.fields["icon_class"].help_text = "Chỉ cần nhập khi bạn chọn mục “Tự nhập mã icon khác”."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        cleaned_data["icon_class"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="icon_choice",
            actual_name="icon_class",
            default_value="fas fa-certificate",
        )
        return cleaned_data


class AboutPageSlideForm(BootstrapModelForm):
    link_choice = forms.ChoiceField(required=False, label="Liên kết nhanh", choices=())

    class Meta:
        model = AboutPageSlide
        fields = ["image", "alt_text", "link_url", "sort_order", "is_active"]
        widgets = {
            "image": forms.FileInput(attrs={"accept": "image/*"}),
            "alt_text": forms.TextInput(attrs={"placeholder": "Mô tả ngắn cho ảnh slide"}),
            "link_url": forms.TextInput(attrs={"placeholder": "Ví dụ: /products/"}),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "image": "Ảnh slide",
            "alt_text": "Mô tả ảnh",
            "link_url": "Liên kết khi bấm",
            "sort_order": "Thứ tự",
            "is_active": "Hiển thị slide này",
        }

    def __init__(self, *args, **kwargs):
        link_choices = kwargs.pop("link_choices", [])
        super().__init__(*args, **kwargs)
        self.fields["link_url"].required = False
        current_link = self.initial.get("link_url") or getattr(self.instance, "link_url", "")
        configure_quick_select_field(
            self,
            choice_name="link_choice",
            actual_name="link_url",
            option_pairs=link_choices,
            empty_label="Chọn nhanh một liên kết",
            custom_label="Tự nhập liên kết khác",
            current_value=current_link,
        )
        self.fields["link_url"].label = "Liên kết tùy chỉnh"
        self.fields["link_url"].help_text = "Chỉ cần nhập ô này khi bạn chọn mục “Tự nhập liên kết khác”."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        cleaned_data["link_url"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="link_choice",
            actual_name="link_url",
            default_value="",
        )

        has_other_data = any(
            str(cleaned_data.get(field_name) or "").strip()
            for field_name in ("alt_text", "link_url")
        ) or bool(cleaned_data.get("image"))
        has_existing_image = bool(getattr(self.instance, "image", None) or getattr(self.instance, "legacy_static_path", ""))
        if has_other_data and not (cleaned_data.get("image") or has_existing_image):
            raise forms.ValidationError("Mỗi slide cần có ảnh hiển thị hoặc ảnh dự phòng sẵn có.")
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.cleaned_data.get("image"):
            obj.legacy_static_path = ""
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class AboutFeaturedBranchItemForm(BootstrapModelForm):
    link_choice = forms.ChoiceField(required=False, label="Liên kết nhanh", choices=())

    class Meta:
        model = AboutFeaturedBranchItem
        fields = [
            "pharmacy",
            "badge",
            "map_note",
            "link_url",
            "link_label",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "pharmacy": forms.Select(),
            "badge": forms.TextInput(attrs={"placeholder": "Ví dụ: Điểm bán nổi bật"}),
            "map_note": forms.TextInput(attrs={"placeholder": "Ví dụ: Có thể mở trực tiếp trên bản đồ"}),
            "link_url": forms.TextInput(attrs={"placeholder": "Ví dụ: /pharmacy/1/ hoặc /map/?pharmacy_id=1"}),
            "link_label": forms.TextInput(attrs={"placeholder": "Ví dụ: Xem chi nhánh"}),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "pharmacy": "Chọn chi nhánh từ hệ thống",
            "badge": "Nhãn nổi trên ảnh",
            "map_note": "Ghi chú phụ",
            "link_url": "Liên kết tùy chỉnh",
            "link_label": "Nhãn nút liên kết",
            "sort_order": "Thứ tự",
            "is_active": "Hiển thị thẻ này",
        }

    def __init__(self, *args, **kwargs):
        link_choices = kwargs.pop("link_choices", [])
        super().__init__(*args, **kwargs)
        self.order_fields(["pharmacy", "badge", "map_note", "link_choice", "link_url", "link_label", "sort_order", "is_active"])
        self.fields["pharmacy"].queryset = Pharmacy.objects.order_by("name")
        self.fields["pharmacy"].empty_label = "Chọn một chi nhánh"
        self.fields["pharmacy"].help_text = "Danh sách này lấy trực tiếp từ phần quản lý chi nhánh của hệ thống."
        self.fields["link_url"].required = False
        current_link = self.initial.get("link_url") or getattr(self.instance, "link_url", "")
        configure_quick_select_field(
            self,
            choice_name="link_choice",
            actual_name="link_url",
            option_pairs=link_choices,
            empty_label="Chọn nhanh một liên kết",
            custom_label="Tự nhập liên kết khác",
            current_value=current_link,
        )
        self.fields["link_url"].help_text = "Chỉ cần nhập ô này khi bạn chọn mục “Tự nhập liên kết khác”."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        cleaned_data["link_url"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="link_choice",
            actual_name="link_url",
            default_value="",
        )
        pharmacy = cleaned_data.get("pharmacy")
        if pharmacy is not None:
            cleaned_data["title"] = pharmacy.name
            cleaned_data["summary"] = ""
            cleaned_data["address"] = pharmacy.address
            cleaned_data["hours"] = pharmacy.opening_hours
            cleaned_data["icon_class"] = "fas fa-clinic-medical"
            cleaned_data["image"] = getattr(pharmacy, "image", None)
            if not cleaned_data["link_url"]:
                cleaned_data["link_url"] = f"/pharmacy/{pharmacy.pk}/"
        cleaned_data["link_label"] = str(cleaned_data.get("link_label") or "").strip() or "Xem chi nhánh"
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        pharmacy = self.cleaned_data.get("pharmacy")
        if pharmacy is not None:
            obj.title = pharmacy.name
            obj.summary = ""
            obj.address = pharmacy.address
            obj.hours = pharmacy.opening_hours
            obj.icon_class = "fas fa-clinic-medical"
            obj.image = getattr(pharmacy, "image", None)
            if not obj.link_url:
                obj.link_url = f"/pharmacy/{pharmacy.pk}/"
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class AboutCustomBlockForm(BootstrapModelForm):
    icon_choice = forms.ChoiceField(required=False, label="Chọn icon", choices=())
    link_choice = forms.ChoiceField(required=False, label="Liên kết nhanh", choices=())

    class Meta:
        model = AboutCustomBlock
        fields = [
            "kicker",
            "title",
            "body",
            "icon_class",
            "link_url",
            "link_label",
            "sort_order",
            "is_active",
        ]
        widgets = {
            "kicker": forms.TextInput(attrs={"placeholder": "Ví dụ: Dành cho giảng viên"}),
            "title": forms.TextInput(attrs={"placeholder": "Ví dụ: Khối nội dung mới trên trang Giới thiệu"}),
            "body": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Nhập nội dung cho khối mới. Có thể dùng rich text để định dạng đoạn văn, danh sách, tiêu đề nhỏ...",
                    "data-rich-editor": "1",
                }
            ),
            "icon_class": forms.TextInput(attrs={"placeholder": "Ví dụ: fas fa-layer-group"}),
            "link_url": forms.TextInput(attrs={"placeholder": "Ví dụ: /news/ hoặc /products/"}),
            "link_label": forms.TextInput(attrs={"placeholder": "Ví dụ: Xem thêm"}),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "kicker": "Nhãn nhỏ",
            "title": "Tiêu đề khối",
            "body": "Nội dung",
            "icon_class": "Mã icon tùy chỉnh",
            "link_url": "Liên kết tùy chỉnh",
            "link_label": "Nhãn nút",
            "sort_order": "Thứ tự",
            "is_active": "Hiển thị khối này",
        }

    def __init__(self, *args, **kwargs):
        icon_choices = kwargs.pop("icon_choices", HOME_ICON_OPTION_PAIRS)
        link_choices = kwargs.pop("link_choices", [])
        super().__init__(*args, **kwargs)
        self.order_fields(["kicker", "title", "body", "icon_choice", "icon_class", "link_choice", "link_url", "link_label", "sort_order", "is_active"])
        self.fields["icon_class"].required = False
        self.fields["link_url"].required = False
        current_icon = self.initial.get("icon_class") or getattr(self.instance, "icon_class", "") or "fas fa-layer-group"
        current_link = self.initial.get("link_url") or getattr(self.instance, "link_url", "")
        configure_quick_select_field(
            self,
            choice_name="icon_choice",
            actual_name="icon_class",
            option_pairs=icon_choices,
            empty_label="Chọn nhanh một icon",
            custom_label="Tự nhập mã icon khác",
            current_value=current_icon,
        )
        configure_quick_select_field(
            self,
            choice_name="link_choice",
            actual_name="link_url",
            option_pairs=link_choices,
            empty_label="Chọn nhanh một liên kết",
            custom_label="Tự nhập liên kết khác",
            current_value=current_link,
        )
        self.fields["icon_class"].help_text = "Chỉ cần nhập khi bạn chọn mục “Tự nhập mã icon khác”."
        self.fields["link_url"].help_text = "Chỉ cần nhập ô này khi bạn chọn mục “Tự nhập liên kết khác”."

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get("DELETE"):
            return cleaned_data
        cleaned_data["icon_class"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="icon_choice",
            actual_name="icon_class",
            default_value="fas fa-layer-group",
        )
        cleaned_data["link_url"] = resolve_quick_select_value(
            cleaned_data,
            choice_name="link_choice",
            actual_name="link_url",
            default_value="",
        )
        return cleaned_data


class BaseAboutBuiltinSectionFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return

        seen_section_keys = {}
        for form in self.forms:
            if not hasattr(form, "cleaned_data") or not form.cleaned_data:
                continue
            if form.cleaned_data.get("DELETE"):
                continue

            section_key = str(form.cleaned_data.get("section_key") or "").strip()
            if not section_key:
                continue
            if section_key in seen_section_keys:
                raise forms.ValidationError("Mỗi khối hệ thống chỉ được xuất hiện một lần trong bố cục trang Giới thiệu.")
            seen_section_keys[section_key] = True


class AboutBuiltinSectionForm(BootstrapModelForm):
    class Meta:
        model = AboutBuiltinSection
        fields = ["section_key", "sort_order"]
        widgets = {
            "section_key": forms.Select(),
            "sort_order": forms.NumberInput(attrs={"min": 0, "step": 1}),
        }
        labels = {
            "section_key": "Khối hệ thống",
            "sort_order": "Thứ tự hiển thị",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.order_fields(["section_key", "sort_order"])
        self.fields["section_key"].help_text = (
            "Xóa dòng này nếu không muốn khối xuất hiện ngoài trang Giới thiệu. "
            "Muốn thêm lại thì tạo dòng mới và chọn đúng loại khối."
        )


HomeHeroSlideFormSet = inlineformset_factory(
    HomePageContent,
    HomeHeroSlide,
    form=HomeHeroSlideForm,
    extra=0,
    can_delete=True,
)

HomeCategorySpotlightItemFormSet = inlineformset_factory(
    HomePageContent,
    HomeCategorySpotlightItem,
    form=HomeCategorySpotlightItemForm,
    extra=0,
    can_delete=True,
)

HomeServiceCommitmentItemFormSet = inlineformset_factory(
    HomePageContent,
    HomeServiceCommitmentItem,
    form=HomeServiceCommitmentItemForm,
    extra=0,
    can_delete=True,
)

AboutPageSlideFormSet = inlineformset_factory(
    AboutPageContent,
    AboutPageSlide,
    form=AboutPageSlideForm,
    extra=0,
    can_delete=True,
)

AboutFeaturedBranchItemFormSet = inlineformset_factory(
    AboutPageContent,
    AboutFeaturedBranchItem,
    form=AboutFeaturedBranchItemForm,
    extra=0,
    can_delete=True,
)

AboutCustomBlockFormSet = inlineformset_factory(
    AboutPageContent,
    AboutCustomBlock,
    form=AboutCustomBlockForm,
    extra=0,
    can_delete=True,
)

AboutBuiltinSectionFormSet = inlineformset_factory(
    AboutPageContent,
    AboutBuiltinSection,
    form=AboutBuiltinSectionForm,
    formset=BaseAboutBuiltinSectionFormSet,
    extra=0,
    can_delete=True,
)


class PharmacyAdminForm(BootstrapModelForm):
    gallery_images = MultipleImageField(
        required=False,
        label="Tải thư viện ảnh",
        widget=MultipleImageInput(attrs={"class": "image-file-input", "accept": "image/*", "multiple": True}),
    )
    open_time = forms.TimeField(
        required=True,
        label="Giờ mở cửa",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
    )
    close_time = forms.TimeField(
        required=True,
        label="Giờ đóng cửa",
        input_formats=["%H:%M"],
        widget=forms.TimeInput(format="%H:%M", attrs={"type": "time"}),
    )
    delete_image = forms.BooleanField(required=False, widget=forms.HiddenInput())
    delete_gallery = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Pharmacy
        fields = ["name", "address", "phone", "desc", "image", "gallery_urls", "lat", "lng"]
        widgets = {
            "desc": forms.Textarea(
                attrs={
                    "rows": 16,
                    "placeholder": "Mô tả dài về chi nhánh, dịch vụ hoặc điểm nổi bật...",
                    "data-rich-editor": "1",
                }
            ),
            "gallery_urls": forms.HiddenInput(),
            "lat": forms.NumberInput(attrs={"step": "any", "placeholder": "Ví dụ: 10.8231", "readonly": "readonly"}),
            "lng": forms.NumberInput(attrs={"step": "any", "placeholder": "Ví dụ: 106.6297", "readonly": "readonly"}),
            "phone": forms.TextInput(attrs={"placeholder": "Ví dụ: 0901234567"}),
            "address": forms.TextInput(attrs={"placeholder": "Nhập địa chỉ chi nhánh"}),
            "image": forms.FileInput(attrs={"class": "image-file-input", "accept": "image/*"}),
        }
        labels = {
            "name": "Tên chi nhánh",
            "address": "Địa chỉ",
            "phone": "Số điện thoại",
            "desc": "Mô tả dịch vụ",
            "image": "Ảnh chi nhánh",
            "lat": "Vĩ độ",
            "lng": "Kinh độ",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if self.instance and self.instance.pk and self.instance.opening_hours:
            try:
                normalized = self.instance.opening_hours.replace("–", "-").replace("—", "-")
                open_str, close_str = [part.strip() for part in normalized.split("-", 1)]
                self.fields["open_time"].initial = datetime.strptime(open_str, "%H:%M").time()
                self.fields["close_time"].initial = datetime.strptime(close_str, "%H:%M").time()
            except Exception:
                self.fields["open_time"].initial = datetime.strptime("08:00", "%H:%M").time()
                self.fields["close_time"].initial = datetime.strptime("22:00", "%H:%M").time()
        else:
            self.fields["open_time"].initial = datetime.strptime("08:00", "%H:%M").time()
            self.fields["close_time"].initial = datetime.strptime("22:00", "%H:%M").time()

        for field_name in ("lat", "lng"):
            self.fields[field_name].widget.attrs["readonly"] = "readonly"
            self.fields[field_name].widget.attrs["autocomplete"] = "off"
            self.fields[field_name].widget.attrs["inputmode"] = "decimal"
            self.fields[field_name].widget.attrs["data-coordinate-locked"] = "1"


    def clean(self):
        cleaned_data = super().clean()
        open_time = cleaned_data.get("open_time")
        close_time = cleaned_data.get("close_time")

        if open_time and close_time and close_time <= open_time:
            raise forms.ValidationError("Giờ đóng cửa phải lớn hơn giờ mở cửa.")

        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        open_time = self.cleaned_data.get("open_time")
        close_time = self.cleaned_data.get("close_time")

        if open_time and close_time:
            obj.opening_hours = f"{open_time.strftime('%H:%M')} - {close_time.strftime('%H:%M')}"

        if self.cleaned_data.get("delete_image") and getattr(obj, "image", None):
            obj.image.delete(save=False)
            obj.image = None

        gallery_files = [uploaded for uploaded in self.files.getlist("gallery_images") if uploaded]
        has_gallery_customization = any(str(key).startswith("gallery_keep_") for key in self.data.keys()) or any(
            str(key).startswith("gallery_replace_") for key in self.files.keys()
        )
        if gallery_files or self.cleaned_data.get("delete_gallery") or has_gallery_customization or getattr(obj, "pk", None):
            obj.gallery_urls = "\n".join(
                merge_gallery_storage_names(
                    getattr(self.instance, "gallery_urls", ""),
                    data=self.data,
                    files=self.files,
                    folder="pharmacies/gallery",
                    append_files=gallery_files,
                    remove_all=bool(self.cleaned_data.get("delete_gallery")),
                )
            )

        if commit:
            obj.save()
            self.save_m2m()

        return obj


class MedicineAdminForm(BootstrapModelForm):
    gallery_images = MultipleImageField(
        required=False,
        label="Tải thư viện ảnh",
        widget=MultipleImageInput(attrs={"class": "image-file-input", "accept": "image/*", "multiple": True}),
    )
    product_type = forms.ChoiceField(choices=MEDICINE_PRODUCT_TYPE_CHOICES, required=False, label="Loại sản phẩm")
    category = forms.ChoiceField(choices=MEDICINE_CATEGORY_CHOICES, required=False, label="Danh mục")
    unit = forms.ChoiceField(choices=UNIT_CHOICES, required=True, label="Đơn vị tính")
    delete_image = forms.BooleanField(required=False, widget=forms.HiddenInput())
    delete_gallery = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Medicine
        fields = [
            "pharmacy",
            "name",
            "product_type",
            "category",
            "unit",
            "short_description",
            "manufacturer",
            "origin",
            "price",
            "quantity",
            "expiry_date",
            "image",
            "gallery_urls",
            "description",
            "usage",
            "ingredients",
            "dosage",
            "prescription_required",
        ]
        widgets = {
            "pharmacy": forms.Select(),
            "name": forms.TextInput(attrs={"placeholder": "Nhập tên sản phẩm/thuốc"}),
            "short_description": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "Mô tả ngắn hiển thị bên dưới ảnh ở trang chủ và trang sản phẩm. Chỉ nhập text ngắn gọn, không cần định dạng.",
                }
            ),
            "manufacturer": forms.TextInput(attrs={"placeholder": "Ví dụ: DHG Pharma"}),
            "origin": forms.TextInput(attrs={"placeholder": "Ví dụ: Việt Nam"}),
            "price": forms.NumberInput(attrs={"min": 0, "step": 1000}),
            "quantity": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "expiry_date": forms.DateInput(attrs={"type": "date"}),
            "image": forms.FileInput(attrs={"class": "image-file-input", "accept": "image/*"}),
            "gallery_urls": forms.HiddenInput(),
            "description": forms.Textarea(
                attrs={
                    "rows": 18,
                    "placeholder": "Nhập mô tả chi tiết, có thể định dạng, chèn ảnh và trình bày dài...",
                    "data-rich-editor": "1",
                }
            ),
            "usage": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": "Nhập công dụng của thuốc...",
                    "data-rich-editor": "1",
                }
            ),
            "ingredients": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": "Nhập thành phần chính...",
                    "data-rich-editor": "1",
                }
            ),
            "dosage": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": "Nhập cách dùng, liều dùng...",
                    "data-rich-editor": "1",
                }
            ),
        }
        labels = {
            "pharmacy": "Thuộc chi nhánh",
            "name": "Tên thuốc",
            "product_type": "Loại sản phẩm",
            "short_description": "Mô tả ngắn",
            "manufacturer": "Nhà sản xuất",
            "origin": "Xuất xứ",
            "price": "Đơn giá (VND)",
            "quantity": "Số lượng tồn kho",
            "expiry_date": "Hạn sử dụng",
            "image": "Ảnh thuốc",
            "description": "Mô tả chi tiết",
            "usage": "Công dụng",
            "ingredients": "Thành phần",
            "dosage": "Cách dùng",
            "prescription_required": "Cần kê đơn",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.original_catalog_key = (
            build_medicine_catalog_key(self.instance.name, self.instance.unit, self.instance.manufacturer)
            if getattr(self.instance, "pk", None)
            else None
        )
        self.staff_managed_pharmacy = get_managed_pharmacy_for_user(self.admin_user)
        self.fields["pharmacy"].queryset = Pharmacy.objects.order_by("name")
        self.fields["pharmacy"].empty_label = "Chọn chi nhánh"
        self.fields["short_description"].help_text = "Trường này chỉ hiển thị ở trang chủ và trang danh sách sản phẩm."

        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if self.staff_managed_pharmacy:
                self.fields["pharmacy"].queryset = Pharmacy.objects.filter(pk=self.staff_managed_pharmacy.pk)
                self.fields["pharmacy"].initial = self.staff_managed_pharmacy
                self.fields["pharmacy"].empty_label = None
                self.fields["pharmacy"].help_text = (
                    f"Tài khoản nhân viên này chỉ được quản lý sản phẩm thuộc chi nhánh {self.staff_managed_pharmacy.name}."
                )
            else:
                self.fields["pharmacy"].queryset = Pharmacy.objects.none()
                self.fields["pharmacy"].help_text = "Tài khoản này chưa được gán chi nhánh quản lý."

        current_category = getattr(self.instance, "category", "")
        category_values = [choice[0] for choice in MEDICINE_CATEGORY_CHOICES]
        if current_category and current_category not in category_values:
            self.fields["category"].choices = MEDICINE_CATEGORY_CHOICES + [(current_category, current_category)]

        current_unit = getattr(self.instance, "unit", "")
        unit_values = [choice[0] for choice in UNIT_CHOICES]
        if current_unit and current_unit not in unit_values:
            self.fields["unit"].choices = UNIT_CHOICES + [(current_unit, current_unit)]

        self.fields["quantity"].disabled = True
        self.fields["quantity"].required = False
        self.fields["quantity"].help_text = "Tồn kho được hệ thống tính tự động theo các lô nhập và xuất FEFO, không chỉnh tay trực tiếp tại đây."
        self.fields["expiry_date"].disabled = True
        self.fields["expiry_date"].required = False
        self.fields["expiry_date"].help_text = "HSD tại đây là mốc cảnh báo sớm nhất còn tồn theo các lô của sản phẩm, không chỉnh tay trực tiếp tại đây."
        if not getattr(self.instance, "pk", None):
            self.fields["quantity"].initial = 0


    def clean_pharmacy(self):
        pharmacy = self.cleaned_data.get("pharmacy")
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if not self.staff_managed_pharmacy:
                raise forms.ValidationError("Tài khoản nhân viên chưa được cấp chi nhánh quản lý.")
            return self.staff_managed_pharmacy
        return pharmacy

    def clean_product_type(self):
        product_type = (self.cleaned_data.get("product_type") or "").strip()
        valid_values = {choice[0] for choice in MEDICINE_PRODUCT_TYPE_CHOICES}
        if product_type in valid_values:
            return product_type
        existing_value = (getattr(self.instance, "product_type", "") or "").strip()
        if existing_value in valid_values:
            return existing_value
        return Medicine.TYPE_MEDICINE

    def save(self, commit=True):
        obj = super().save(commit=False)
        if getattr(self, 'staff_managed_pharmacy', None):
            obj.pharmacy = self.staff_managed_pharmacy
        catalog_sync_fields = {field_name for field_name in self.changed_data if field_name in MEDICINE_SHARED_SYNC_FIELDS}
        has_new_main_image = bool(self.files.get("image"))
        should_delete_image = bool(self.cleaned_data.get("delete_image"))
        should_delete_gallery = bool(self.cleaned_data.get("delete_gallery"))

        if should_delete_image and getattr(obj, "image", None):
            obj.image.delete(save=False)
            obj.image = None
            catalog_sync_fields.add("image")
        elif has_new_main_image:
            catalog_sync_fields.add("image")

        gallery_files = [uploaded for uploaded in self.files.getlist("gallery_images") if uploaded]
        has_gallery_customization = any(str(key).startswith("gallery_keep_") for key in self.data.keys()) or any(
            str(key).startswith("gallery_replace_") for key in self.files.keys()
        )
        if gallery_files or should_delete_gallery or has_gallery_customization or getattr(obj, "pk", None):
            merged_gallery_urls = "\n".join(
                merge_gallery_storage_names(
                    getattr(self.instance, "gallery_urls", ""),
                    data=self.data,
                    files=self.files,
                    folder="medicines/gallery",
                    append_files=gallery_files,
                    remove_all=should_delete_gallery,
                )
            )
            if merged_gallery_urls != (getattr(self.instance, "gallery_urls", "") or ""):
                obj.gallery_urls = merged_gallery_urls
                catalog_sync_fields.add("gallery_urls")

        if commit:
            obj.save()
            self.save_m2m()
            if catalog_sync_fields:
                sync_medicine_catalog_metadata(
                    obj,
                    previous_catalog_key=self.original_catalog_key,
                    field_names=catalog_sync_fields,
                )

        return obj





class PromotionAdminForm(BootstrapModelForm):
    class Meta:
        model = MedicinePromotion
        fields = ["medicine", "title", "discount_percent", "start_date", "end_date", "is_active", "note"]
        widgets = {
            "medicine": forms.Select(),
            "title": forms.TextInput(attrs={"placeholder": "Ví dụ: Xả lô cận hạn / Ưu đãi dịp lễ"}),
            "discount_percent": forms.NumberInput(
                attrs={
                    "type": "range",
                    "min": 0,
                    "max": 100,
                    "step": 1,
                    "data-range-output": "discount_percent",
                }
            ),
            "start_date": forms.DateInput(attrs={"type": "date"}),
            "end_date": forms.DateInput(attrs={"type": "date"}),
            "note": forms.Textarea(attrs={"rows": 3, "placeholder": "Ghi chú nội bộ về chương trình giảm giá..."}),
        }
        labels = {
            "medicine": "Sản phẩm áp dụng",
            "title": "Tên chương trình",
            "discount_percent": "Mức giảm (%)",
            "start_date": "Bắt đầu",
            "end_date": "Kết thúc",
            "is_active": "Đang áp dụng",
            "note": "Ghi chú",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.staff_managed_pharmacy = get_managed_pharmacy_for_user(self.admin_user)
        queryset = Medicine.objects.select_related("pharmacy").order_by("name", "id")
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if self.staff_managed_pharmacy:
                queryset = queryset.filter(pharmacy=self.staff_managed_pharmacy)
            else:
                queryset = queryset.none()

        today = timezone.localdate()
        warning_deadline = today + timedelta(days=183)
        grouped = {}
        for medicine in queryset:
            group_key = build_medicine_catalog_key(medicine.name, medicine.unit, medicine.manufacturer)
            entry = grouped.setdefault(group_key, {
                'medicine': medicine,
                'total_stock': 0,
                'warning_stock': 0,
                'nearest_expiry': None,
                'is_warning': False,
            })
            entry['total_stock'] += int(medicine.quantity or 0)
            if medicine.expiry_date:
                if entry['nearest_expiry'] is None or medicine.expiry_date < entry['nearest_expiry']:
                    entry['nearest_expiry'] = medicine.expiry_date
                if today <= medicine.expiry_date <= warning_deadline:
                    entry['warning_stock'] += int(medicine.quantity or 0)
                    entry['is_warning'] = True
            representative_rank = (
                0 if medicine.quantity > 0 else 1,
                -int(medicine.quantity or 0),
                medicine.id,
            )
            current_rank = entry.get('representative_rank')
            if current_rank is None or representative_rank < current_rank:
                entry['representative_rank'] = representative_rank
                entry['medicine'] = medicine

        ordered_entries = sorted(
            grouped.values(),
            key=lambda item: (
                0 if item['is_warning'] else 1,
                -(item['warning_stock'] if item['is_warning'] else item['total_stock']),
                item['nearest_expiry'] or datetime.max.date(),
                item['medicine'].name.casefold(),
            )
        )
        representative_ids = [entry['medicine'].id for entry in ordered_entries]
        representative_queryset = Medicine.objects.select_related("pharmacy").filter(id__in=representative_ids)
        medicine_map = {medicine.id: medicine for medicine in representative_queryset}
        self.fields["medicine"].queryset = representative_queryset

        label_map = {}
        for entry in ordered_entries:
            medicine = medicine_map.get(entry['medicine'].id, entry['medicine'])
            if entry['is_warning']:
                prefix = "[Ưu tiên cận hạn ≤ 6 tháng]"
                stock_text = entry['warning_stock'] or entry['total_stock']
            else:
                prefix = "[Sản phẩm thường]"
                stock_text = entry['total_stock']
            expiry_label = entry['nearest_expiry'].strftime('%d/%m/%Y') if entry['nearest_expiry'] else 'Chưa có HSD'
            label_map[medicine.id] = f"{prefix} {medicine.name} • {medicine.unit or '-'} • Tồn {stock_text} • HSD gần nhất {expiry_label}"

        self.fields["medicine"].choices = [('', '---------')] + [
            (medicine_id, label_map[medicine_id])
            for medicine_id in representative_ids
            if medicine_id in label_map
        ]

        current_instance = getattr(self, 'instance', None)
        if current_instance and getattr(current_instance, 'pk', None) and getattr(current_instance, 'medicine_id', None):
            current_group_key = build_medicine_catalog_key(
                current_instance.medicine.name,
                current_instance.medicine.unit,
                current_instance.medicine.manufacturer,
            )
            for entry in ordered_entries:
                candidate = medicine_map.get(entry['medicine'].id, entry['medicine'])
                if build_medicine_catalog_key(candidate.name, candidate.unit, candidate.manufacturer) == current_group_key:
                    self.initial['medicine'] = candidate.id
                    break

        self.fields["medicine"].help_text = (
            "Mỗi mặt hàng chỉ hiện một dòng đại diện. Hệ thống ưu tiên gợi ý các mặt hàng còn tồn lớn và có HSD gần trong 6 tháng."
        )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get("start_date")
        end_date = cleaned_data.get("end_date")
        discount_percent = cleaned_data.get("discount_percent")
        if start_date and end_date and end_date < start_date:
            self.add_error("end_date", "Ngày kết thúc phải lớn hơn hoặc bằng ngày bắt đầu.")
        if discount_percent is None or discount_percent < 0 or discount_percent > 100:
            self.add_error("discount_percent", "Mức giảm phải nằm trong khoảng từ 0% đến 100%.")
        medicine = cleaned_data.get("medicine")
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if not self.staff_managed_pharmacy:
                raise forms.ValidationError("Tài khoản nhân viên chưa được gán chi nhánh quản lý.")
            if medicine and medicine.pharmacy_id != self.staff_managed_pharmacy.id:
                self.add_error("medicine", "Bạn chỉ được tạo khuyến mãi cho sản phẩm thuộc chi nhánh mình phụ trách.")

        if medicine and cleaned_data.get("is_active"):
            group_key = build_medicine_catalog_key(medicine.name, medicine.unit, medicine.manufacturer)
            overlapping_promotions = MedicinePromotion.objects.select_related("medicine").exclude(pk=getattr(self.instance, 'pk', None))
            for promotion in overlapping_promotions:
                promo_medicine = getattr(promotion, "medicine", None)
                if promo_medicine is None:
                    continue
                if build_medicine_catalog_key(promo_medicine.name, promo_medicine.unit, promo_medicine.manufacturer) != group_key:
                    continue
                if not promotion.is_active:
                    continue
                other_start = promotion.start_date
                other_end = promotion.end_date
                current_start = start_date
                current_end = end_date
                overlaps = (
                    (current_end is None or other_start is None or other_start <= current_end)
                    and (other_end is None or current_start is None or current_start <= other_end)
                )
                if overlaps:
                    self.add_error("medicine", "Mặt hàng này đã có một chương trình khuyến mãi đang áp dụng hoặc trùng thời gian.")
                    break
        return cleaned_data

    def save(self, commit=True):
        obj = super().save(commit=False)
        if getattr(self, 'admin_user', None) and getattr(self.admin_user, 'is_authenticated', False) and not obj.created_by_id:
            obj.created_by = self.admin_user
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class OrderStatusUpdateForm(BootstrapModelForm):
    STATUS_TRANSITIONS = {
        Order.STATUS_PENDING: {Order.STATUS_PENDING, Order.STATUS_CONFIRMED, Order.STATUS_CANCELLED},
        Order.STATUS_CONFIRMED: {Order.STATUS_CONFIRMED, Order.STATUS_PACKING, Order.STATUS_CANCELLED},
        Order.STATUS_PACKING: {Order.STATUS_PACKING, Order.STATUS_SHIPPING, Order.STATUS_CANCELLED},
        Order.STATUS_SHIPPING: {Order.STATUS_SHIPPING, Order.STATUS_COMPLETED, Order.STATUS_FAILED_DELIVERY},
        Order.STATUS_COMPLETED: {Order.STATUS_COMPLETED},
        Order.STATUS_CANCELLED: {Order.STATUS_CANCELLED},
        Order.STATUS_FAILED_DELIVERY: {Order.STATUS_FAILED_DELIVERY},
    }

    class Meta:
        model = Order
        fields = [
            "pharmacy",
            "status",
            "payment_status",
            "payment_proof_image",
            "payment_note",
            "prescription_status",
            "prescription_admin_note",
        ]
        widgets = {
            "pharmacy": forms.Select(),
            "status": forms.Select(),
            "payment_status": forms.Select(),
            "payment_proof_image": forms.FileInput(attrs={"accept": "image/*"}),
            "payment_note": forms.Textarea(attrs={"rows": 3, "placeholder": "Ghi chú đối soát thanh toán..."}),
            "prescription_status": forms.Select(),
            "prescription_admin_note": forms.Textarea(attrs={"rows": 3, "placeholder": "Ghi chú duyệt đơn thuốc..."}),
        }
        labels = {
            "pharmacy": "Chi nhánh xử lý",
            "status": "Trạng thái đơn",
            "payment_status": "Trạng thái thanh toán",
            "payment_proof_image": "Ảnh chứng từ thanh toán",
            "payment_note": "Ghi chú thanh toán",
            "prescription_status": "Trạng thái đơn thuốc",
            "prescription_admin_note": "Ghi chú duyệt đơn thuốc",
        }

    def __init__(self, *args, **kwargs):
        instance = kwargs.get("instance")
        data = args[0] if args else kwargs.get("data")
        if data is not None and hasattr(data, "copy") and instance is not None:
            mutable_data = data.copy()
            mutable_data.setdefault("payment_status", getattr(instance, "payment_status", Order.PAYMENT_STATUS_COD_WAITING))
            mutable_data.setdefault("prescription_status", getattr(instance, "prescription_status", Order.PRESCRIPTION_STATUS_NOT_REQUIRED))
            if args:
                args = (mutable_data, *args[1:])
            else:
                kwargs["data"] = mutable_data
        super().__init__(*args, **kwargs)
        self.staff_managed_pharmacy = get_managed_pharmacy_for_user(self.admin_user)
        self.fields["pharmacy"].queryset = Pharmacy.objects.order_by("name")
        self.fields["pharmacy"].required = False
        self.fields["pharmacy"].empty_label = "Chưa gán chi nhánh"
        if instance is not None and getattr(instance, "pk", None) and instance.items.exists():
            self.fields["pharmacy"].help_text = (
                "Đơn đã có chi tiết sản phẩm và tồn kho đã được phân bổ theo chi nhánh hiện tại. "
                "Không đổi trực tiếp chi nhánh để tránh lệch tồn kho, phí giao hàng và lô FEFO."
            )
        self.fields["status"].widget.attrs["class"] = "form-control form-control-lg"
        self.fields["payment_status"].help_text = "Với chuyển khoản/MoMo, phải xác nhận đã thanh toán trước khi chuyển sang giao hàng."
        self.fields["prescription_status"].help_text = "Đơn có thuốc kê đơn phải được duyệt trước khi chuẩn bị/giao hàng."

        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if self.staff_managed_pharmacy:
                self.fields["pharmacy"].queryset = Pharmacy.objects.filter(pk=self.staff_managed_pharmacy.pk)
                self.fields["pharmacy"].initial = self.staff_managed_pharmacy
                self.fields["pharmacy"].empty_label = None
                self.fields["pharmacy"].help_text = (
                    f"Nhân viên chỉ được xử lý đơn thuộc chi nhánh {self.staff_managed_pharmacy.name}."
                )
            else:
                self.fields["pharmacy"].queryset = Pharmacy.objects.none()
                self.fields["pharmacy"].help_text = "Tài khoản nhân viên chưa được gán chi nhánh quản lý."

    def clean_payment_proof_image(self):
        payment_proof_image = self.cleaned_data.get("payment_proof_image")
        if not payment_proof_image:
            return payment_proof_image
        return validate_image_like_upload(payment_proof_image)

    def clean_pharmacy(self):
        pharmacy = self.cleaned_data.get("pharmacy")
        if self.admin_user and self.admin_user.is_staff and not self.admin_user.is_superuser:
            if not self.staff_managed_pharmacy:
                raise forms.ValidationError("Tài khoản nhân viên chưa được cấp chi nhánh quản lý.")
            return self.staff_managed_pharmacy
        if self.instance and getattr(self.instance, "pk", None):
            current_pharmacy_id = getattr(self.instance, "pharmacy_id", None)
            next_pharmacy_id = getattr(pharmacy, "pk", None)
            if current_pharmacy_id != next_pharmacy_id and self.instance.items.exists():
                raise forms.ValidationError(
                    "Không thể đổi chi nhánh xử lý sau khi đơn đã có sản phẩm và tồn kho đã được phân bổ. "
                    "Nếu cần điều phối sang chi nhánh khác, hãy hủy đơn hiện tại rồi tạo đơn mới để hệ thống tính lại tồn kho, lô FEFO, phí giao hàng và hóa đơn."
                )
        return pharmacy

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get("status")
        payment_status = cleaned_data.get("payment_status")
        prescription_status = cleaned_data.get("prescription_status")
        current_status = getattr(self.instance, "status", Order.STATUS_PENDING)
        payment_method = getattr(self.instance, "payment_method", Order.PAYMENT_COD)

        allowed_statuses = self.STATUS_TRANSITIONS.get(current_status, {current_status})
        if status and status not in allowed_statuses:
            self.add_error(
                "status",
                f"Không thể chuyển trạng thái từ '{self.instance.get_status_display()}' sang '{dict(Order.STATUS_CHOICES).get(status, status)}'.",
            )

        if payment_method == Order.PAYMENT_COD and payment_status == Order.PAYMENT_STATUS_AWAITING_TRANSFER:
            self.add_error("payment_status", "Đơn COD không dùng trạng thái chờ chuyển khoản.")
        if payment_method in {Order.PAYMENT_BANK, Order.PAYMENT_MOMO} and payment_status == Order.PAYMENT_STATUS_COD_WAITING:
            self.add_error("payment_status", "Đơn chuyển khoản/MoMo phải ở trạng thái chờ xác nhận hoặc đã thanh toán.")

        shipping_like_statuses = {Order.STATUS_SHIPPING, Order.STATUS_COMPLETED}
        if (
            status in shipping_like_statuses
            and payment_method in {Order.PAYMENT_BANK, Order.PAYMENT_MOMO}
            and payment_status != Order.PAYMENT_STATUS_PAID
        ):
            self.add_error("payment_status", "Cần xác nhận đã thanh toán trước khi giao hoặc hoàn thành đơn non-COD.")

        has_prescription_images = bool(getattr(self.instance, "prescription_proof_image", None))
        if not has_prescription_images and getattr(self.instance, "pk", None):
            try:
                has_prescription_images = self.instance.prescription_proof_images.exists()
            except Exception:
                has_prescription_images = False

        prescription_required = (
            getattr(self.instance, "requires_prescription_review", False)
            or has_prescription_images
            or prescription_status != Order.PRESCRIPTION_STATUS_NOT_REQUIRED
        )
        if status in {Order.STATUS_PACKING, Order.STATUS_SHIPPING, Order.STATUS_COMPLETED}:
            if prescription_required and prescription_status != Order.PRESCRIPTION_STATUS_APPROVED:
                self.add_error("prescription_status", "Đơn có thuốc kê đơn phải được duyệt hợp lệ trước khi chuẩn bị hoặc giao hàng.")

        return cleaned_data

    def save(self, commit=True):
        order = super().save(commit=False)
        previous_payment_status = None
        previous_prescription_status = None
        if self.instance and self.instance.pk:
            previous_payment_status = getattr(self.instance, "_loaded_payment_status", None) or Order.objects.filter(pk=self.instance.pk).values_list("payment_status", flat=True).first()
            previous_prescription_status = getattr(self.instance, "_loaded_prescription_status", None) or Order.objects.filter(pk=self.instance.pk).values_list("prescription_status", flat=True).first()

        if getattr(self, 'staff_managed_pharmacy', None):
            order.pharmacy = self.staff_managed_pharmacy
        now = timezone.now()
        if order.payment_status == Order.PAYMENT_STATUS_PAID:
            if previous_payment_status != Order.PAYMENT_STATUS_PAID or order.payment_confirmed_at is None:
                order.payment_confirmed_at = now
                if self.admin_user and getattr(self.admin_user, "is_authenticated", False):
                    order.payment_confirmed_by = self.admin_user
        elif previous_payment_status == Order.PAYMENT_STATUS_PAID:
            order.payment_confirmed_at = None
            order.payment_confirmed_by = None

        if order.prescription_status in {Order.PRESCRIPTION_STATUS_APPROVED, Order.PRESCRIPTION_STATUS_REJECTED}:
            if previous_prescription_status != order.prescription_status or order.prescription_reviewed_at is None:
                order.prescription_reviewed_at = now
                if self.admin_user and getattr(self.admin_user, "is_authenticated", False):
                    order.prescription_reviewed_by = self.admin_user
        elif order.prescription_status == Order.PRESCRIPTION_STATUS_PENDING:
            order.prescription_reviewed_at = None
            order.prescription_reviewed_by = None
        elif order.prescription_status == Order.PRESCRIPTION_STATUS_NOT_REQUIRED:
            order.prescription_reviewed_at = None
            order.prescription_reviewed_by = None
            order.prescription_admin_note = ""

        if commit:
            order.save()
        return order


class NewsArticleAdminForm(BootstrapModelForm):
    class Meta:
        model = NewsArticle
        fields = ["title", "slug", "summary", "content", "cover_image", "published_at", "is_published"]
        widgets = {
            "title": forms.TextInput(attrs={"placeholder": "Nhập tiêu đề bài viết"}),
            "slug": forms.TextInput(attrs={"placeholder": "Để trống để hệ thống tự tạo"}),
            "summary": forms.Textarea(
                attrs={
                    "rows": 8,
                    "placeholder": "Nhập phần tóm tắt ngắn cho bài viết...",
                    "data-rich-editor": "1",
                }
            ),
            "content": forms.Textarea(
                attrs={
                    "rows": 18,
                    "placeholder": "Nhập nội dung chi tiết, có thể định dạng và chèn ảnh...",
                    "data-rich-editor": "1",
                }
            ),
            "cover_image": forms.FileInput(attrs={"accept": "image/*"}),
            "published_at": forms.DateTimeInput(attrs={"type": "datetime-local"}),
        }
        labels = {
            "title": "Tiêu đề",
            "slug": "Slug đường dẫn",
            "summary": "Tóm tắt",
            "content": "Nội dung chi tiết",
            "cover_image": "Ảnh đại diện",
            "published_at": "Thời điểm xuất bản",
            "is_published": "Xuất bản bài viết",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk and self.instance.published_at:
            local_dt = timezone.localtime(self.instance.published_at)
            self.initial.setdefault("published_at", local_dt.strftime("%Y-%m-%dT%H:%M"))

    def save(self, commit=True):
        obj = super().save(commit=False)
        if self.admin_user and getattr(self.admin_user, "is_authenticated", False):
            if not obj.pk and not obj.created_by_id:
                obj.created_by = self.admin_user
            obj.updated_by = self.admin_user
        if obj.is_published and not obj.published_at:
            obj.published_at = timezone.now()
        if commit:
            obj.save()
            self.save_m2m()
        return obj


class CustomUserCreateForm(VietnameseValidationMixin, UserCreationForm):
    email = forms.EmailField(required=False, label="Email", widget=forms.EmailInput())
    first_name = forms.CharField(required=False, label="Tên", widget=forms.TextInput())
    last_name = forms.CharField(required=False, label="Họ", widget=forms.TextInput())
    is_active = forms.BooleanField(required=False, label="Kích hoạt tài khoản", initial=True)
    role = forms.ChoiceField(required=False, label="Vai trò truy cập", choices=USER_ROLE_CHOICES, widget=forms.Select())
    managed_pharmacy = forms.ModelChoiceField(
        required=False,
        label="Chi nhánh phụ trách",
        queryset=Pharmacy.objects.order_by("name"),
        empty_label="Chưa gán chi nhánh",
        help_text="Bắt buộc với tài khoản nhân viên. Mỗi nhân viên chỉ quản lý một chi nhánh duy nhất.",
    )

    password1 = forms.CharField(label="Mật khẩu", widget=forms.PasswordInput())
    password2 = forms.CharField(label="Nhập lại mật khẩu", widget=forms.PasswordInput())

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_active"]
        labels = {"username": "Tên đăng nhập"}
        widgets = {"username": forms.TextInput()}

    def __init__(self, *args, **kwargs):
        self.admin_user = kwargs.pop("admin_user", None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            else:
                old_class = widget.attrs.get("class", "").strip()
                widget.attrs["class"] = f"{old_class} form-control".strip()

        self.fields["username"].widget.attrs["placeholder"] = "Nhập tên đăng nhập"
        self.fields["role"].widget.attrs["class"] = "form-control"
        self.fields["managed_pharmacy"].widget.attrs["class"] = "form-control"
        self.order_fields(
            [
                "username",
                "email",
                "first_name",
                "last_name",
                "password1",
                "password2",
                "role",
                "managed_pharmacy",
                "is_active",
            ]
        )

        if self.admin_user and self.admin_user.is_superuser:
            self.fields["role"].initial = "customer"
        else:
            self.fields.pop("role", None)
            self.fields.pop("managed_pharmacy", None)

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role") or "customer"
        managed_pharmacy = cleaned_data.get("managed_pharmacy")
        if self.admin_user and self.admin_user.is_superuser and role == "staff" and managed_pharmacy is None:
            self.add_error("managed_pharmacy", "Hãy chọn chi nhánh mà nhân viên này sẽ phụ trách.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        role = "customer"

        if self.admin_user and self.admin_user.is_superuser:
            role = self.cleaned_data.get("role") or "customer"
            user.is_staff = role in {"staff", "superuser"}
            user.is_superuser = role == "superuser"
        else:
            user.is_staff = False
            user.is_superuser = False

        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or user.username,
                    "phone": "",
                    "address_text": "",
                },
            )
            profile.managed_pharmacy = self.cleaned_data.get("managed_pharmacy") if role == "staff" else None
            if role != "staff":
                profile.admin_permissions = {}
            profile.save(update_fields=["managed_pharmacy", "admin_permissions", "updated_at"])

        return user


class CustomUserUpdateForm(VietnameseValidationMixin, forms.ModelForm):
    role = forms.ChoiceField(required=False, label="Vai trò truy cập", choices=USER_ROLE_CHOICES, widget=forms.Select())
    managed_pharmacy = forms.ModelChoiceField(
        required=False,
        label="Chi nhánh phụ trách",
        queryset=Pharmacy.objects.order_by("name"),
        empty_label="Chưa gán chi nhánh",
        help_text="Bắt buộc với tài khoản nhân viên. Nếu đổi sang vai trò khác, chi nhánh phụ trách sẽ được bỏ trống.",
    )
    new_password = forms.CharField(
        required=False,
        label="Mật khẩu mới",
        widget=forms.PasswordInput(
            attrs={
                "autocomplete": "new-password",
                "placeholder": "Để trống nếu không đổi mật khẩu",
                "data-lpignore": "true",
            }
        ),
        help_text="Chỉ nhập khi quản trị viên muốn đặt lại mật khẩu cho tài khoản này.",
    )

    class Meta:
        model = User
        fields = ["username", "email", "first_name", "last_name", "is_active"]
        labels = {
            "username": "Tên đăng nhập",
            "email": "Email",
            "first_name": "Tên",
            "last_name": "Họ",
            "is_active": "Kích hoạt tài khoản",
        }
        widgets = {
            "username": forms.TextInput(),
            "email": forms.EmailInput(),
            "first_name": forms.TextInput(),
            "last_name": forms.TextInput(),
        }

    def __init__(self, *args, **kwargs):
        self.admin_user = kwargs.pop("admin_user", None)
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            widget = field.widget
            if isinstance(widget, forms.CheckboxInput):
                widget.attrs["class"] = "form-check-input"
            else:
                old_class = widget.attrs.get("class", "").strip()
                widget.attrs["class"] = f"{old_class} form-control".strip()

        self.fields["role"].widget.attrs["class"] = "form-control"
        self.fields["managed_pharmacy"].widget.attrs["class"] = "form-control"
        if self.instance.is_superuser:
            self.fields["role"].initial = "superuser"
        elif self.instance.is_staff:
            self.fields["role"].initial = "staff"
        else:
            self.fields["role"].initial = "customer"

        existing_profile = None
        if self.instance.pk:
            existing_profile, _ = UserProfile.objects.get_or_create(
                user=self.instance,
                defaults={
                    "full_name": self.instance.get_full_name() or self.instance.username,
                    "phone": "",
                    "address_text": "",
                },
            )
            self.fields["managed_pharmacy"].initial = existing_profile.managed_pharmacy

        self.order_fields(
            [
                "username",
                "email",
                "first_name",
                "last_name",
                "new_password",
                "role",
                "managed_pharmacy",
                "is_active",
            ]
        )

        if not (self.admin_user and self.admin_user.is_superuser):
            self.fields.pop("role", None)
            self.fields.pop("managed_pharmacy", None)

    def clean_new_password(self):
        password_value = (self.cleaned_data.get("new_password") or "").strip()
        if password_value and self.instance and self.instance.pk and self.instance.check_password(password_value):
            raise ValidationError("Mật khẩu mới không được trùng với mật khẩu đang dùng trước đó.")
        return password_value

    def clean(self):
        cleaned_data = super().clean()
        role = cleaned_data.get("role") or ("superuser" if self.instance.is_superuser else "staff" if self.instance.is_staff else "customer")
        managed_pharmacy = cleaned_data.get("managed_pharmacy")
        if self.admin_user and self.admin_user.is_superuser and role == "staff" and managed_pharmacy is None:
            self.add_error("managed_pharmacy", "Hãy chọn chi nhánh mà nhân viên này sẽ phụ trách.")
        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("new_password")
        role = "superuser" if self.instance.is_superuser else "staff" if self.instance.is_staff else "customer"

        if self.admin_user and self.admin_user.is_superuser:
            role = self.cleaned_data.get("role") or "customer"
            user.is_staff = role in {"staff", "superuser"}
            user.is_superuser = role == "superuser"
        else:
            user.is_staff = getattr(self.instance, "is_staff", False)
            user.is_superuser = getattr(self.instance, "is_superuser", False)

        if pw:
            user.set_password(pw)

        if commit:
            user.save()
            profile, _ = UserProfile.objects.get_or_create(
                user=user,
                defaults={
                    "full_name": user.get_full_name() or user.username,
                    "phone": "",
                    "address_text": "",
                },
            )
            profile.managed_pharmacy = self.cleaned_data.get("managed_pharmacy") if role == "staff" else None
            if role != "staff":
                profile.admin_permissions = {}
            profile.save(update_fields=["managed_pharmacy", "admin_permissions", "updated_at"])

        return user
class ExistingEmailPasswordResetForm(VietnameseValidationMixin, PasswordResetForm):
    email = forms.EmailField(
        label="Email",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "placeholder": "Nhập email đã đăng ký",
            }
        ),
    )

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        has_matching_user = User.objects.filter(
            email__iexact=email,
            is_active=True,
        ).exists()
        if not has_matching_user:
            raise ValidationError("Không tìm thấy tài khoản nào sử dụng email này.")
        return email


class AccountRecoveryRequestForm(VietnameseValidationMixin, forms.Form):
    email = forms.EmailField(
        label="Email đã đăng ký",
        widget=forms.EmailInput(
            attrs={
                "class": "form-control",
                "autocomplete": "email",
                "placeholder": "Nhập email bạn đã dùng để đăng ký tài khoản",
            }
        ),
    )

    def __init__(self, *args, **kwargs):
        self.recovery_mode = kwargs.pop("recovery_mode", "password")
        self.matched_user = None
        super().__init__(*args, **kwargs)

    def clean_email(self):
        email = (self.cleaned_data.get("email") or "").strip()
        self.matched_user = (
            User.objects.filter(email__iexact=email, is_active=True).order_by("id").first()
        )
        if self.matched_user is None:
            raise ValidationError("Không tìm thấy tài khoản nào sử dụng email này.")
        return email


class PasswordResetOtpVerificationForm(VietnameseValidationMixin, PasswordReuseValidationMixin, SetPasswordForm):
    otp_code = forms.CharField(
        label="Mã OTP",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "placeholder": "Nhập 6 số OTP",
                "maxlength": "6",
            }
        ),
    )

    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Hai mật khẩu nhập vào không khớp.",
    }

    def __init__(self, user, *args, **kwargs):
        super().__init__(user, *args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập mật khẩu mới",
                "data-password-toggle": "1",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập lại mật khẩu mới",
                "data-password-toggle": "1",
            }
        )

    def clean_otp_code(self):
        otp_code = re.sub(r"\D+", "", (self.cleaned_data.get("otp_code") or "").strip())
        if len(otp_code) != 6:
            raise ValidationError("Mã OTP phải gồm đúng 6 chữ số.")
        return otp_code


class UsernameRecoveryOtpVerificationForm(VietnameseValidationMixin, forms.Form):
    otp_code = forms.CharField(
        label="Mã OTP",
        min_length=6,
        max_length=6,
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "inputmode": "numeric",
                "autocomplete": "one-time-code",
                "placeholder": "Nhập 6 số OTP",
                "maxlength": "6",
            }
        ),
    )

    def clean_otp_code(self):
        otp_code = re.sub(r"\D+", "", (self.cleaned_data.get("otp_code") or "").strip())
        if len(otp_code) != 6:
            raise ValidationError("Mã OTP phải gồm đúng 6 chữ số.")
        return otp_code


class StyledSetPasswordForm(VietnameseValidationMixin, PasswordReuseValidationMixin, SetPasswordForm):
    error_messages = {
        **SetPasswordForm.error_messages,
        "password_mismatch": "Hai mật khẩu nhập vào không khớp.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["new_password1"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập mật khẩu mới",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập lại mật khẩu mới",
            }
        )


class ProfilePasswordChangeForm(VietnameseValidationMixin, PasswordReuseValidationMixin, PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "Mật khẩu hiện tại không đúng.",
        "password_mismatch": "Hai mật khẩu mới nhập vào không khớp.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["old_password"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "current-password",
                "placeholder": "Nhập mật khẩu hiện tại",
            }
        )
        self.fields["new_password1"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập mật khẩu mới",
            }
        )
        self.fields["new_password2"].widget.attrs.update(
            {
                "class": "form-control",
                "autocomplete": "new-password",
                "placeholder": "Nhập lại mật khẩu mới",
            }
        )
