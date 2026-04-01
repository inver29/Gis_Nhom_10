from datetime import datetime
from pathlib import Path
from uuid import uuid4

from django import forms
from django.conf import settings
from django.core.files.storage import default_storage
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User

from .models import Medicine, Order, Pharmacy, UserProfile


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


def build_media_url(saved_name):
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
        uploaded_urls.append(build_media_url(saved_name))

    return uploaded_urls


class CheckoutForm(forms.ModelForm):
    class Meta:
        model = Order
        fields = ["full_name", "phone", "address_text", "note"]
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


class RegisterForm(forms.ModelForm):
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


class LoginForm(forms.Form):
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


class AccountProfileForm(forms.Form):
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


class BootstrapModelForm(forms.ModelForm):
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
                attrs={"rows": 5, "placeholder": "Mô tả ngắn về chi nhánh, dịch vụ hoặc điểm nổi bật..."}
            ),
            "gallery_urls": forms.HiddenInput(),
            "lat": forms.NumberInput(attrs={"step": "any", "placeholder": "Ví dụ: 10.8231"}),
            "lng": forms.NumberInput(attrs={"step": "any", "placeholder": "Ví dụ: 106.6297"}),
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
        if gallery_files:
            obj.gallery_urls = "\n".join(save_uploaded_gallery_files(gallery_files, "pharmacies/gallery"))
        elif self.cleaned_data.get("delete_gallery"):
            obj.gallery_urls = ""

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
    category = forms.ChoiceField(choices=MEDICINE_CATEGORY_CHOICES, required=False, label="Danh mục")
    unit = forms.ChoiceField(choices=UNIT_CHOICES, required=True, label="Đơn vị tính")
    delete_image = forms.BooleanField(required=False, widget=forms.HiddenInput())
    delete_gallery = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Medicine
        fields = [
            "pharmacy",
            "name",
            "category",
            "unit",
            "manufacturer",
            "origin",
            "price",
            "quantity",
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
            "manufacturer": forms.TextInput(attrs={"placeholder": "Ví dụ: DHG Pharma"}),
            "origin": forms.TextInput(attrs={"placeholder": "Ví dụ: Việt Nam"}),
            "price": forms.NumberInput(attrs={"min": 0, "step": 1000}),
            "quantity": forms.NumberInput(attrs={"min": 0, "step": 1}),
            "image": forms.FileInput(attrs={"class": "image-file-input", "accept": "image/*"}),
            "gallery_urls": forms.HiddenInput(),
            "description": forms.Textarea(attrs={"rows": 4, "placeholder": "Mô tả ngắn về sản phẩm..."}),
            "usage": forms.Textarea(attrs={"rows": 4, "placeholder": "Nhập công dụng của thuốc..."}),
            "ingredients": forms.Textarea(attrs={"rows": 4, "placeholder": "Nhập thành phần chính..."}),
            "dosage": forms.Textarea(attrs={"rows": 4, "placeholder": "Nhập cách dùng, liều dùng..."}),
        }
        labels = {
            "pharmacy": "Thuộc chi nhánh",
            "name": "Tên thuốc",
            "manufacturer": "Nhà sản xuất",
            "origin": "Xuất xứ",
            "price": "Đơn giá (VND)",
            "quantity": "Số lượng tồn kho",
            "image": "Ảnh thuốc",
            "description": "Mô tả ngắn",
            "usage": "Công dụng",
            "ingredients": "Thành phần",
            "dosage": "Cách dùng",
            "prescription_required": "Cần kê đơn",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pharmacy"].queryset = Pharmacy.objects.order_by("name")
        self.fields["pharmacy"].empty_label = "Chọn chi nhánh"

        current_category = getattr(self.instance, "category", "")
        category_values = [choice[0] for choice in MEDICINE_CATEGORY_CHOICES]
        if current_category and current_category not in category_values:
            self.fields["category"].choices = MEDICINE_CATEGORY_CHOICES + [(current_category, current_category)]

        current_unit = getattr(self.instance, "unit", "")
        unit_values = [choice[0] for choice in UNIT_CHOICES]
        if current_unit and current_unit not in unit_values:
            self.fields["unit"].choices = UNIT_CHOICES + [(current_unit, current_unit)]

    def save(self, commit=True):
        obj = super().save(commit=False)
        has_new_main_image = bool(self.files.get("image"))
        should_delete_image = bool(self.cleaned_data.get("delete_image"))
        should_delete_gallery = bool(self.cleaned_data.get("delete_gallery"))

        if should_delete_image and getattr(obj, "image", None):
            obj.image.delete(save=False)
            obj.image = None

        gallery_files = [uploaded for uploaded in self.files.getlist("gallery_images") if uploaded]
        if gallery_files:
            obj.gallery_urls = "\n".join(save_uploaded_gallery_files(gallery_files, "medicines/gallery"))
        elif should_delete_gallery:
            obj.gallery_urls = ""

        if commit:
            obj.save()
            self.save_m2m()

            should_sync_media = has_new_main_image or bool(gallery_files) or should_delete_image or should_delete_gallery
            if should_sync_media:
                Medicine.objects.filter(
                    name__iexact=obj.name,
                    unit__iexact=obj.unit,
                    manufacturer__iexact=obj.manufacturer,
                ).exclude(pk=obj.pk).update(
                    image=(obj.image.name if obj.image else ""),
                    gallery_urls=obj.gallery_urls,
                )

        return obj



class OrderStatusUpdateForm(BootstrapModelForm):
    class Meta:
        model = Order
        fields = ["pharmacy", "status"]
        widgets = {
            "pharmacy": forms.Select(),
            "status": forms.Select(),
        }
        labels = {
            "pharmacy": "Chi nhánh xử lý",
            "status": "Trạng thái đơn",
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["pharmacy"].queryset = Pharmacy.objects.order_by("name")
        self.fields["pharmacy"].required = False
        self.fields["pharmacy"].empty_label = "Chưa gán chi nhánh"
        self.fields["status"].widget.attrs["class"] = "form-control form-control-lg"


class CustomUserCreateForm(UserCreationForm):
    email = forms.EmailField(required=False, label="Email", widget=forms.EmailInput())
    first_name = forms.CharField(required=False, label="Tên", widget=forms.TextInput())
    last_name = forms.CharField(required=False, label="Họ", widget=forms.TextInput())
    is_active = forms.BooleanField(required=False, label="Kích hoạt tài khoản", initial=True)
    role = forms.ChoiceField(required=False, label="Vai trò truy cập", choices=USER_ROLE_CHOICES, widget=forms.Select())

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
        self.order_fields(
            [
                "username",
                "email",
                "first_name",
                "last_name",
                "password1",
                "password2",
                "role",
                "is_active",
            ]
        )

        if self.admin_user and self.admin_user.is_superuser:
            self.fields["role"].initial = "customer"
        else:
            self.fields.pop("role", None)

    def save(self, commit=True):
        user = super().save(commit=False)

        if self.admin_user and self.admin_user.is_superuser:
            role = self.cleaned_data.get("role") or "customer"
            user.is_staff = role in {"staff", "superuser"}
            user.is_superuser = role == "superuser"
        else:
            user.is_staff = False
            user.is_superuser = False

        if commit:
            user.save()

        return user


class CustomUserUpdateForm(forms.ModelForm):
    role = forms.ChoiceField(required=False, label="Vai trò truy cập", choices=USER_ROLE_CHOICES, widget=forms.Select())
    new_password = forms.CharField(required=False, label="Mật khẩu mới", widget=forms.PasswordInput())
    confirm_new_password = forms.CharField(required=False, label="Nhập lại mật khẩu mới", widget=forms.PasswordInput())

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
        if self.instance.is_superuser:
            self.fields["role"].initial = "superuser"
        elif self.instance.is_staff:
            self.fields["role"].initial = "staff"
        else:
            self.fields["role"].initial = "customer"

        self.order_fields(
            [
                "username",
                "email",
                "first_name",
                "last_name",
                "new_password",
                "confirm_new_password",
                "role",
                "is_active",
            ]
        )

        if not (self.admin_user and self.admin_user.is_superuser):
            self.fields.pop("role", None)

    def clean(self):
        cleaned_data = super().clean()
        pw1 = cleaned_data.get("new_password")
        pw2 = cleaned_data.get("confirm_new_password")

        if pw1 or pw2:
            if pw1 != pw2:
                raise forms.ValidationError("Mật khẩu mới không khớp")

        return cleaned_data

    def save(self, commit=True):
        user = super().save(commit=False)
        pw = self.cleaned_data.get("new_password")

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

        return user
