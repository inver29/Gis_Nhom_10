from uuid import uuid4
from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=150, verbose_name="Ho ten hien thi", blank=True)
    phone = models.CharField(max_length=20, verbose_name="So dien thoai", blank=True)
    address_text = models.CharField(max_length=255, verbose_name="Dia chi mac dinh", blank=True)
    address_lat = models.FloatField(verbose_name="Vi do mac dinh", null=True, blank=True)
    address_lng = models.FloatField(verbose_name="Kinh do mac dinh", null=True, blank=True)
    managed_pharmacy = models.ForeignKey(
        "Pharmacy",
        on_delete=models.SET_NULL,
        related_name="managed_staff_profiles",
        verbose_name="Chi nhanh lam viec",
        null=True,
        blank=True,
    )
    admin_permissions = models.JSONField(default=dict, blank=True, verbose_name="Phan quyen quan tri chi tiet")
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.username

    @property
    def has_saved_address(self):
        return bool(self.address_text and self.address_lat is not None and self.address_lng is not None)

    class Meta:
        verbose_name = "Ho so tai khoan"
        verbose_name_plural = "Ho so tai khoan"


class AccountOtpChallenge(models.Model):
    PURPOSE_PASSWORD_RESET = "password_reset"
    PURPOSE_USERNAME_RECOVERY = "username_recovery"
    PURPOSE_REGISTRATION = "registration"
    PURPOSE_CHOICES = (
        (PURPOSE_PASSWORD_RESET, "Đặt lại mật khẩu"),
        (PURPOSE_USERNAME_RECOVERY, "Khôi phục tên đăng nhập"),
        (PURPOSE_REGISTRATION, "Kích hoạt tài khoản đăng ký"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="account_otp_challenges",
        verbose_name="Tài khoản",
    )
    purpose = models.CharField(
        max_length=40,
        choices=PURPOSE_CHOICES,
        db_index=True,
        verbose_name="Mục đích xác thực",
    )
    email = models.EmailField(db_index=True, verbose_name="Email nhận mã")
    public_token = models.UUIDField(
        default=uuid4,
        unique=True,
        editable=False,
        db_index=True,
        verbose_name="Mã công khai của phiên OTP",
    )
    otp_hash = models.CharField(max_length=255, verbose_name="Mã OTP đã băm")
    username_snapshot = models.CharField(max_length=150, blank=True, default="", verbose_name="Tên đăng nhập snapshot")
    expires_at = models.DateTimeField(db_index=True, verbose_name="Thời điểm hết hạn")
    attempts = models.PositiveSmallIntegerField(default=0, verbose_name="Số lần nhập sai")
    consumed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thời điểm đã dùng xong")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời điểm tạo")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Thời điểm cập nhật")

    def __str__(self):
        return f"{self.get_purpose_display()} - {self.email}"

    @property
    def is_expired(self):
        return bool(self.expires_at and self.expires_at <= timezone.now())

    @property
    def is_consumed(self):
        return self.consumed_at is not None

    @property
    def is_active(self):
        return not self.is_consumed and not self.is_expired

    class Meta:
        verbose_name = "Phiên OTP khôi phục tài khoản"
        verbose_name_plural = "Phiên OTP khôi phục tài khoản"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["purpose", "email"], name="idx_otp_purpose_email"),
            models.Index(fields=["user", "purpose"], name="idx_otp_user_purpose"),
        ]
        

