from datetime import timedelta
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from django.db.models import Avg, Q
from django.utils import timezone
from ..model_helpers import (
    build_gallery_urls,
    build_gallery_urls_from_text,
    build_medicine_catalog_key,
)
from ..storage import build_db_media_url


MEDICINE_PRODUCT_TYPE_MEDICINE = "medicine"
MEDICINE_PRODUCT_TYPE_SUPPLEMENT = "supplement"
MEDICINE_PRODUCT_TYPE_CHOICES = (
    (MEDICINE_PRODUCT_TYPE_MEDICINE, "Thuốc"),
    (MEDICINE_PRODUCT_TYPE_SUPPLEMENT, "Thực phẩm chức năng"),
)


class Pharmacy(models.Model):
    name = models.CharField(max_length=200, verbose_name="Ten nha thuoc")
    address = models.CharField(max_length=255, verbose_name="Dia chi")
    phone = models.CharField(max_length=20, verbose_name="So dien thoai", default="090xxxxxxx")
    opening_hours = models.CharField(max_length=100, verbose_name="Gio mo cua", default="8:00 - 22:00")
    desc = models.TextField(verbose_name="Mo ta dich vu", blank=True)
    image = models.ImageField(upload_to="pharmacies/", verbose_name="Hinh anh", null=True, blank=True)
    gallery_urls = models.TextField(verbose_name="Bo suu tap anh", blank=True)
    lat = models.FloatField(verbose_name="Vi do")
    lng = models.FloatField(verbose_name="Kinh do")

    def __str__(self):
        return self.name

    @property
    def has_available_medicines(self):
        return self.medicines.filter(quantity__gt=0).exists()

    @property
    def gallery_only_image_list(self):
        return build_gallery_urls_from_text(self.gallery_urls)

    @property
    def gallery_image_list(self):
        return build_gallery_urls(self)

    @property
    def primary_image_url(self):
        return self.gallery_image_list[0] if self.gallery_image_list else ""

    @property
    def average_rating(self):
        return round(self.reviews.aggregate(avg=Avg('rating')).get('avg') or 0, 1)

    @property
    def review_count(self):
        return self.reviews.count()

    class Meta:
        verbose_name = "Chi nhanh"
        verbose_name_plural = "Quan ly Chi nhanh"
        ordering = ["name"]


class PharmacyReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="pharmacy_reviews")
    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        verbose_name="So sao",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(verbose_name="Cam nhan", blank=True)
    is_edited = models.BooleanField(default=False, verbose_name="Da cap nhat lai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.pharmacy.name} ({self.rating} sao)"

    @property
    def was_updated_by_user(self):
        return bool(self.is_edited)

    class Meta:
        verbose_name = "Danh gia chi nhanh"
        verbose_name_plural = "Danh gia chi nhanh"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "pharmacy"], name="unique_user_pharmacy_review"),
        ]


class Medicine(models.Model):
    TYPE_MEDICINE = MEDICINE_PRODUCT_TYPE_MEDICINE
    TYPE_SUPPLEMENT = MEDICINE_PRODUCT_TYPE_SUPPLEMENT

    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="medicines",
        verbose_name="Thuoc chi nhanh",
    )
    name = models.CharField(max_length=200, verbose_name="Ten thuoc")
    product_type = models.CharField(
        max_length=20,
        choices=MEDICINE_PRODUCT_TYPE_CHOICES,
        default=MEDICINE_PRODUCT_TYPE_MEDICINE,
        verbose_name="Loai san pham",
    )
    category = models.CharField(max_length=100, verbose_name="Danh muc", blank=True)
    unit = models.CharField(max_length=50, verbose_name="Don vi tinh", default="Hop")
    manufacturer = models.CharField(max_length=150, verbose_name="Nha san xuat", blank=True)
    origin = models.CharField(max_length=150, verbose_name="Xuat xu", blank=True)
    price = models.IntegerField(verbose_name="Don gia (VND)")
    quantity = models.PositiveIntegerField(verbose_name="So luong ton kho", default=0)
    image = models.ImageField(upload_to="medicines/", verbose_name="Anh thuoc", null=True, blank=True)
    gallery_urls = models.TextField(verbose_name="Bo suu tap anh", blank=True)
    short_description = models.CharField(max_length=280, verbose_name="Mo ta ngan hien thi ngoai danh sach", blank=True, default="")
    description = models.TextField(verbose_name="Mo ta chi tiet", blank=True)
    usage = models.TextField(verbose_name="Cong dung", blank=True)
    ingredients = models.TextField(verbose_name="Thanh phan", blank=True)
    dosage = models.TextField(verbose_name="Cach dung", blank=True)
    prescription_required = models.BooleanField(verbose_name="Can ke don", default=False)
    expiry_date = models.DateField(verbose_name="Han su dung", null=True, blank=True)

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.quantity > 0

    @property
    def gallery_only_image_list(self):
        return build_gallery_urls_from_text(self.gallery_urls)

    @property
    def gallery_image_list(self):
        return build_gallery_urls(self)

    @property
    def primary_image_url(self):
        return self.gallery_image_list[0] if self.gallery_image_list else ""

    @property
    def average_rating(self):
        return round(self.reviews.aggregate(avg=Avg('rating')).get('avg') or 0, 1)

    @property
    def review_count(self):
        return self.reviews.count()

    @property
    def expiry_status(self):
        if not self.expiry_date:
            return "unknown"
        today = timezone.localdate()
        if self.expiry_date < today:
            return "expired"
        six_months_later = today + timedelta(days=183)
        if self.expiry_date <= six_months_later:
            return "warning"
        return "safe"

    @property
    def expiry_days_remaining(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    def get_active_promotion(self, *, on_date=None):
        today = on_date or timezone.localdate()
        prefetched = getattr(self, '_prefetched_active_promotions', None)
        if prefetched is not None:
            return prefetched[0] if prefetched else None

        catalog_promotion = getattr(self, '_catalog_group_active_promotion', None)
        if catalog_promotion is not None:
            return catalog_promotion

        target_key = build_medicine_catalog_key(self.name, self.unit, self.manufacturer)
        promotions = MedicinePromotion.objects.select_related('medicine').filter(
            is_active=True,
        ).filter(
            Q(start_date__isnull=True) | Q(start_date__lte=today),
            Q(end_date__isnull=True) | Q(end_date__gte=today),
        ).order_by('-discount_percent', '-id')

        for promotion in promotions:
            medicine = getattr(promotion, 'medicine', None)
            if medicine is None:
                continue
            if build_medicine_catalog_key(medicine.name, medicine.unit, medicine.manufacturer) == target_key:
                self._catalog_group_active_promotion = promotion
                return promotion

        self._catalog_group_active_promotion = None
        return None

    @property
    def active_promotion(self):
        return self.get_active_promotion()

    @property
    def current_price(self):
        promotion = self.get_active_promotion()
        if not promotion:
            return self.price
        discounted = int(self.price * (100 - promotion.discount_percent) / 100)
        return max(discounted, 0)

    @property
    def has_active_discount(self):
        return self.current_price < self.price

    @property
    def discount_percent(self):
        promotion = self.get_active_promotion()
        return promotion.discount_percent if promotion else 0

    class Meta:
        verbose_name = "San pham thuoc"
        verbose_name_plural = "Kho Thuoc va San pham"
        ordering = ["name"]


class MedicinePromotion(models.Model):
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="promotions", verbose_name="Sản phẩm áp dụng")
    title = models.CharField(max_length=150, blank=True, default="", verbose_name="Tên chương trình")
    discount_percent = models.PositiveSmallIntegerField(verbose_name="Phần trăm giảm", validators=[MinValueValidator(0), MaxValueValidator(100)])
    start_date = models.DateField(null=True, blank=True, verbose_name="Ngày bắt đầu")
    end_date = models.DateField(null=True, blank=True, verbose_name="Ngày kết thúc")
    is_active = models.BooleanField(default=True, verbose_name="Đang áp dụng")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chú")
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name="medicine_promotions", verbose_name="Người tạo")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title or f"Giảm {self.discount_percent}% - {self.medicine.name}"

    @property
    def is_currently_active(self):
        today = timezone.localdate()
        if not self.is_active:
            return False
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

    @property
    def resolved_title(self):
        return (self.title or '').strip() or f"Giảm {self.discount_percent}%"

    class Meta:
        verbose_name = "Khuyến mãi sản phẩm"
        verbose_name_plural = "Khuyến mãi sản phẩm"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=["is_active", "start_date", "end_date"], name="idx_medpromo_active"),
        ]


class MedicineReview(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="medicine_reviews")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE, related_name="reviews")
    rating = models.PositiveSmallIntegerField(
        verbose_name="So sao",
        validators=[MinValueValidator(1), MaxValueValidator(5)],
    )
    comment = models.TextField(verbose_name="Cam nhan", blank=True)
    is_edited = models.BooleanField(default=False, verbose_name="Da cap nhat lai")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.medicine.name} ({self.rating} sao)"

    @property
    def was_updated_by_user(self):
        return bool(self.is_edited)

    class Meta:
        verbose_name = "Danh gia san pham"
        verbose_name_plural = "Danh gia san pham"
        ordering = ["-updated_at", "-id"]
        constraints = [
            models.UniqueConstraint(fields=["user", "medicine"], name="unique_user_medicine_review"),
        ]


class StoredMediaFile(models.Model):
    file_name = models.CharField(max_length=500, unique=True, db_index=True)
    content_type = models.CharField(max_length=255, blank=True)
    file_size = models.PositiveIntegerField(default=0)
    file_data = models.BinaryField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.file_name

    @property
    def public_url(self):
        return build_db_media_url(self.file_name)

    class Meta:
        verbose_name = "Tệp media trong PostgreSQL"
        verbose_name_plural = "Tệp media trong PostgreSQL"
        ordering = ["file_name"]

