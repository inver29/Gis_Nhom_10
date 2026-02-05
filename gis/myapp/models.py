from django.db import models

class Pharmacy(models.Model):
    name = models.CharField(max_length=200, verbose_name="Tên Nhà thuốc")
    address = models.CharField(max_length=255, verbose_name="Địa chỉ")
    phone = models.CharField(max_length=20, verbose_name="Số điện thoại", default="090xxxxxxx")
    opening_hours = models.CharField(max_length=100, verbose_name="Giờ mở cửa", default="8:00 - 22:00")
    desc = models.TextField(verbose_name="Thuốc & Dịch vụ", blank=True)
    has_stock = models.BooleanField(default=True, verbose_name="Còn thuốc")
    image = models.ImageField(upload_to='pharmacies/', verbose_name="Hình ảnh", null=True, blank=True)
    lat = models.FloatField(verbose_name="Vĩ độ")
    lng = models.FloatField(verbose_name="Kinh độ")

    def __str__(self):
        return self.name
    
    class Meta:
        verbose_name = "Nhà thuốc"
        verbose_name_plural = "Danh sách Nhà thuốc"

class Branch(models.Model):
    name = models.CharField(max_length=200)
    address = models.CharField(max_length=300)

    def __str__(self):
        return self.name


class Medicine(models.Model):
    pharmacy = models.ForeignKey(
        Pharmacy,
        on_delete=models.CASCADE,
        related_name='medicines',
        verbose_name='Nhà thuốc'
    )
    name = models.CharField(max_length=200, verbose_name='Tên thuốc')
    price = models.IntegerField(verbose_name='Đơn giá (VNĐ)')
    quantity = models.IntegerField(verbose_name='Số lượng')

    def __str__(self):
        return self.name


class Order(models.Model):
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE)
    medicine = models.ForeignKey(Medicine, on_delete=models.CASCADE)
    quantity = models.IntegerField()
    total_price = models.IntegerField()
    created_at = models.DateTimeField(auto_now_add=True)