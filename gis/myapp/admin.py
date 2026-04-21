from django.contrib import admin
from django.utils.html import format_html

from .models import Medicine, Order, OrderItem, Pharmacy


admin.site.site_header = "HỆ THỐNG QUẢN TRỊ NHÀ THUỐC"
admin.site.site_title = "Admin Pharma"
admin.site.index_title = "Bảng điều khiển trung tâm"


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ('medicine_name', 'price', 'quantity', 'line_total_display')
    verbose_name = "Sản phẩm trong đơn"
    verbose_name_plural = "Danh sách thuốc khách đặt"

    def has_add_permission(self, request, obj=None):
        return False

    def line_total_display(self, obj):
        return f"{obj.line_total:,} đ"

    line_total_display.short_description = "Thành tiền"


@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    list_display = ('name', 'address', 'phone', 'available_stock_status')
    search_fields = ('name', 'address', 'phone')

    def available_stock_status(self, obj):
        if obj.has_available_medicines:
            return 'Còn hàng'
        return 'Hết hàng'

    available_stock_status.short_description = 'Tồn kho'


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'pharmacy', 'price_vnd', 'quantity', 'image_preview')
    list_filter = ('pharmacy',)
    search_fields = ('name',)
    list_per_page = 20

    def price_vnd(self, obj):
        return f"{obj.price:,} đ"

    price_vnd.short_description = "Giá bán"

    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="width: 40px; height:40px; border-radius:5px; object-fit: cover;" />',
                obj.image.url,
            )
        return ""

    image_preview.short_description = "Ảnh"


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at_display', 'customer_display', 'pharmacy', 'total_display', 'status')
    list_editable = ('status',)
    list_filter = ('status', 'created_at', 'pharmacy')
    search_fields = ('id', 'phone', 'full_name')
    inlines = [OrderItemInline]
    readonly_fields = (
        'user',
        'full_name',
        'phone',
        'address_text',
        'note',
        'delivery_lat',
        'delivery_lng',
        'distance_km',
        'shipping_fee',
        'total_product_price',
        'final_total_price',
        'created_at',
        'pharmacy',
    )

    def created_at_display(self, obj):
        return obj.created_at.strftime("%H:%M %d/%m")

    created_at_display.short_description = "Ngày đặt"

    def customer_display(self, obj):
        return format_html("<b>{}</b><br><span style='color:#666'>{}</span>", obj.full_name, obj.phone)

    customer_display.short_description = "Khách hàng"

    def total_display(self, obj):
        return f"{obj.final_total_price:,} đ"

    total_display.short_description = "Tổng thu"

    def has_add_permission(self, request):
        return False