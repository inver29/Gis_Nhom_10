from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from django.db.models.signals import pre_save
from django.dispatch import receiver
from urllib.parse import quote


def encode_public_url(raw_url):
    clean_url = (raw_url or "").strip()
    if not clean_url:
        return ""
    return quote(clean_url, safe='/:?=&%')


def resolve_media_url(image_field):
    if not image_field:
        return ""

    raw_name = ""
    try:
        raw_name = (image_field.name or "").strip()
    except Exception:
        raw_name = str(image_field).strip()

    if raw_name.startswith(("http://", "https://", "/")):
        return encode_public_url(raw_name)

    try:
        return encode_public_url(image_field.url)
    except Exception:
        return encode_public_url(raw_name)


def normalize_gallery_url(raw_url):
    clean_url = (raw_url or "").strip()
    if not clean_url:
        return ""

    if clean_url.startswith(("http://", "https://", "/")):
        return encode_public_url(clean_url)

    media_url = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
    return encode_public_url(f"{media_url}/{clean_url.lstrip('/')}" )


def build_gallery_urls_from_text(raw_text):
    urls = []
    for raw_url in (raw_text or "").splitlines():
        clean_url = normalize_gallery_url(raw_url)
        if clean_url and clean_url not in urls:
            urls.append(clean_url)
    return urls


def build_gallery_urls(instance):
    urls = []

    primary_url = resolve_media_url(getattr(instance, "image", None))
    if primary_url:
        urls.append(primary_url)

    for clean_url in build_gallery_urls_from_text(getattr(instance, "gallery_urls", "") or ""):
        if clean_url not in urls:
            urls.append(clean_url)

    return urls


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

    class Meta:
        verbose_name = "Chi nhanh"
        verbose_name_plural = "Quan ly Chi nhanh"
        ordering = ["name"]


class Medicine(models.Model):
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name="medicines",
        verbose_name="Thuoc chi nhanh",
    )
    name = models.CharField(max_length=200, verbose_name="Ten thuoc")
    category = models.CharField(max_length=100, verbose_name="Danh muc", blank=True)
    unit = models.CharField(max_length=50, verbose_name="Don vi tinh", default="Hop")
    manufacturer = models.CharField(max_length=150, verbose_name="Nha san xuat", blank=True)
    origin = models.CharField(max_length=150, verbose_name="Xuat xu", blank=True)
    price = models.IntegerField(verbose_name="Don gia (VND)")
    quantity = models.PositiveIntegerField(verbose_name="So luong ton kho", default=0)
    image = models.ImageField(upload_to="medicines/", verbose_name="Anh thuoc", null=True, blank=True)
    gallery_urls = models.TextField(verbose_name="Bo suu tap anh", blank=True)
    description = models.TextField(verbose_name="Mo ta ngan", blank=True)
    usage = models.TextField(verbose_name="Cong dung", blank=True)
    ingredients = models.TextField(verbose_name="Thanh phan", blank=True)
    dosage = models.TextField(verbose_name="Cach dung", blank=True)
    prescription_required = models.BooleanField(verbose_name="Can ke don", default=False)

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

    class Meta:
        verbose_name = "San pham thuoc"
        verbose_name_plural = "Kho Thuoc va San pham"
        ordering = ["name"]


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.select_related("medicine").all())

    class Meta:
        verbose_name = "Gio hang tam"
        verbose_name_plural = "Gio hang dang hoat dong"
        constraints = [
            models.UniqueConstraint(
                fields=["session_key"],
                condition=Q(session_key__isnull=False),
                name="unique_cart_session_key",
            ),
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total_price(self):
        return self.medicine.price * self.quantity

    class Meta:
        verbose_name = "San pham trong gio"
        verbose_name_plural = "San pham trong gio"
        constraints = [
            models.UniqueConstraint(fields=["cart", "medicine"], name="unique_cart_medicine")
        ]


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SHIPPING = "shipping"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Cho xu ly"),
        (STATUS_SHIPPING, "Dang giao hang"),
        (STATUS_COMPLETED, "Hoan thanh"),
        (STATUS_CANCELLED, "Da huy"),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tai khoan khach")
    full_name = models.CharField(max_length=100, verbose_name="Nguoi nhan")
    phone = models.CharField(max_length=20, verbose_name="SDT lien he")
    address_text = models.CharField(max_length=255, verbose_name="Dia chi giao")
    note = models.TextField(verbose_name="Ghi chu cua khach", blank=True, null=True)

    delivery_lat = models.FloatField(verbose_name="Vi do", null=True, blank=True)
    delivery_lng = models.FloatField(verbose_name="Kinh do", null=True, blank=True)

    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.SET_NULL, null=True, verbose_name="Chi nhanh xu ly")

    distance_km = models.FloatField(default=0, verbose_name="Khoang cach (km)")
    shipping_fee = models.IntegerField(default=0, verbose_name="Phi ship")
    total_product_price = models.IntegerField(default=0, verbose_name="Tien hang")
    final_total_price = models.IntegerField(default=0, verbose_name="Tong thanh toan")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Trang thai don")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian dat")

    def __str__(self):
        return f"Don #{self.id} - {self.full_name}"

    class Meta:
        verbose_name = "Don hang"
        verbose_name_plural = "Xu ly Don hang"
        ordering = ["-created_at", "-id"]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True)
    medicine_name = models.CharField(max_length=200)
    price = models.IntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.price * self.quantity

    class Meta:
        verbose_name = "Chi tiet san pham"
        verbose_name_plural = "Chi tiet san pham"


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    full_name = models.CharField(max_length=150, verbose_name="Ho ten hien thi", blank=True)
    phone = models.CharField(max_length=20, verbose_name="So dien thoai", blank=True)
    address_text = models.CharField(max_length=255, verbose_name="Dia chi mac dinh", blank=True)
    address_lat = models.FloatField(verbose_name="Vi do mac dinh", null=True, blank=True)
    address_lng = models.FloatField(verbose_name="Kinh do mac dinh", null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.full_name or self.user.username

    @property
    def has_saved_address(self):
        return bool(self.address_text and self.address_lat is not None and self.address_lng is not None)

    class Meta:
        verbose_name = "Ho so tai khoan"
        verbose_name_plural = "Ho so tai khoan"


@receiver(pre_save, sender=Order)
def sync_inventory_when_order_status_changes(sender, instance, **kwargs):
    if not instance.pk:
        return

    previous_status = (
        sender.objects.filter(pk=instance.pk).values_list('status', flat=True).first()
    )
    if previous_status is None or previous_status == instance.status:
        return

    from .views import sync_inventory_for_order_status_transition

    sync_inventory_for_order_status_transition(
        order=instance,
        previous_status=previous_status,
        next_status=instance.status,
    )
