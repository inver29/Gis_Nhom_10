from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q


class Pharmacy(models.Model):
    name = models.CharField(max_length=200, verbose_name="Tên nhà thuốc")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ")
    phone = models.CharField(max_length=20, verbose_name="Số điện thoại", default="090xxxxxxx")
    opening_hours = models.CharField(max_length=100, verbose_name="Giờ mở cửa", default="8:00 - 22:00")
    desc = models.TextField(verbose_name="Mô tả dịch vụ", blank=True)
    image = models.ImageField(upload_to='pharmacies/', verbose_name="Hình ảnh", null=True, blank=True)
    lat = models.FloatField(verbose_name="Vĩ độ")
    lng = models.FloatField(verbose_name="Kinh độ")

    def __str__(self):
        return self.name

    @property
    def has_available_medicines(self):
        return self.medicines.filter(quantity__gt=0).exists()

    class Meta:
        verbose_name = "Chi nhánh"
        verbose_name_plural = "Quản lý Chi nhánh"
        ordering = ['name']


class Medicine(models.Model):
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='medicines',
        verbose_name='Thuộc chi nhánh',
    )
    name = models.CharField(max_length=200, verbose_name='Tên thuốc')
    price = models.IntegerField(verbose_name='Đơn giá (VNĐ)')
    quantity = models.PositiveIntegerField(verbose_name='Số lượng tồn kho', default=0)
    image = models.ImageField(upload_to='medicines/', verbose_name="Ảnh thuốc", null=True, blank=True)
    description = models.TextField(verbose_name="Mô tả", blank=True)

    def __str__(self):
        return self.name

    @property
    def is_in_stock(self):
        return self.quantity > 0

    class Meta:
        verbose_name = "Sản phẩm thuốc"
        verbose_name_plural = "Kho Thuốc & Sản phẩm"
        ordering = ['name']


class Cart(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, null=True, blank=True)
    session_key = models.CharField(max_length=40, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    @property
    def total_price(self):
        return sum(item.total_price for item in self.items.select_related('medicine').all())

    class Meta:
        verbose_name = "Giỏ hàng tạm"
        verbose_name_plural = "Giỏ hàng đang hoạt động"
        constraints = [
            models.UniqueConstraint(
                fields=['session_key'],
                condition=Q(session_key__isnull=False),
                name='unique_cart_session_key',
            ),
        ]


class CartItem(models.Model):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def total_price(self):
        return self.medicine.price * self.quantity

    class Meta:
        verbose_name = "Sản phẩm trong giỏ"
        verbose_name_plural = "Sản phẩm trong giỏ"
        constraints = [
            models.UniqueConstraint(fields=['cart', 'medicine'], name='unique_cart_medicine')
        ]


class Order(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_SHIPPING = 'shipping'
    STATUS_COMPLETED = 'completed'
    STATUS_CANCELLED = 'cancelled'

    STATUS_CHOICES = (
        (STATUS_PENDING, 'Chờ xử lý'),
        (STATUS_SHIPPING, 'Đang giao hàng'),
        (STATUS_COMPLETED, 'Hoàn thành'),
        (STATUS_CANCELLED, 'Đã hủy'),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tài khoản khách")
    full_name = models.CharField(max_length=100, verbose_name="Người nhận")
    phone = models.CharField(max_length=20, verbose_name="SĐT liên hệ")
    address_text = models.CharField(max_length=255, verbose_name="Địa chỉ giao")
    note = models.TextField(verbose_name="Ghi chú của khách", blank=True, null=True)

    delivery_lat = models.FloatField(verbose_name="Vĩ độ", null=True, blank=True)
    delivery_lng = models.FloatField(verbose_name="Kinh độ", null=True, blank=True)

    pharmacy = models.ForeignKey(Pharmacy, on_delete=models.SET_NULL, null=True, verbose_name="Chi nhánh xử lý")

    distance_km = models.FloatField(default=0, verbose_name="Khoảng cách (km)")
    shipping_fee = models.IntegerField(default=0, verbose_name="Phí ship")
    total_product_price = models.IntegerField(default=0, verbose_name="Tiền hàng")
    final_total_price = models.IntegerField(default=0, verbose_name="Tổng thanh toán")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Trạng thái đơn")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thời gian đặt")

    def __str__(self):
        return f"Đơn #{self.id} - {self.full_name}"

    class Meta:
        verbose_name = "Đơn hàng"
        verbose_name_plural = "Xử lý Đơn hàng"
        ordering = ['-created_at']


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    medicine = models.ForeignKey(Medicine, on_delete=models.SET_NULL, null=True)
    medicine_name = models.CharField(max_length=200)
    price = models.IntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.price * self.quantity

    class Meta:
        verbose_name = "Chi tiết sản phẩm"
        verbose_name_plural = "Chi tiết sản phẩm"