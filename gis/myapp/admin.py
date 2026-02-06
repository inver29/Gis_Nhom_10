from django.contrib import admin
from django.contrib.auth.models import User, Group
from django.utils.html import format_html
from django.utils.safestring import mark_safe 
from .models import Pharmacy, Medicine, Order, OrderItem, StaffProfile

# --- CẤU HÌNH TIÊU ĐỀ TRANG ADMIN ---
admin.site.site_header = "HỆ THỐNG QUẢN TRỊ NHÀ THUỐC"
admin.site.site_title = "Admin Pharma"
admin.site.index_title = "Bảng điều khiển trung tâm"

# --- HELPER ---
class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    can_delete = False
    readonly_fields = ('medicine_name', 'price', 'quantity', 'total')
    verbose_name = "Sản phẩm trong đơn"
    verbose_name_plural = "Danh sách thuốc khách đặt"
    
    def has_add_permission(self, request, obj=None): return False

# --- 1. NHÀ THUỐC (ĐÃ SỬA: CHO PHÉP SỬA TRẠNG THÁI) ---
@admin.register(Pharmacy)
class PharmacyAdmin(admin.ModelAdmin):
    # Thay 'status_icon' bằng 'has_stock' để hiển thị dữ liệu thật
    list_display = ('name', 'address', 'phone', 'has_stock')
    
    # [QUAN TRỌNG] Dòng này giúp bạn tích chọn sửa ngay bên ngoài
    list_editable = ('has_stock',)
    
    list_filter = ('has_stock',)
    search_fields = ('name', 'address')

# --- 2. THUỐC ---
@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    list_display = ('name', 'pharmacy', 'price_vnd', 'quantity', 'image_preview')
    list_filter = ('pharmacy',)
    search_fields = ('name',)
    list_per_page = 20
    
    def price_vnd(self, obj): return f"{obj.price:,} đ"
    price_vnd.short_description = "Giá bán"

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="width: 40px; height:40px; border-radius:5px;" />', obj.image.url)
        return ""
    image_preview.short_description = "Ảnh"

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        try: return qs.filter(pharmacy=request.user.staffprofile.pharmacy)
        except: return qs.none()

    def save_model(self, request, obj, form, change):
        if not request.user.is_superuser:
            try: obj.pharmacy = request.user.staffprofile.pharmacy
            except: pass
        super().save_model(request, obj, form, change)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        if not request.user.is_superuser:
            if 'pharmacy' in form.base_fields:
                form.base_fields['pharmacy'].disabled = True
                form.base_fields['pharmacy'].label = ""
                form.base_fields['pharmacy'].widget.attrs['style'] = 'display:none;'
        return form

# --- 3. ĐƠN HÀNG ---
@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_at_fmt', 'customer_info', 'pharmacy', 'total_fmt', 'status')
    list_editable = ('status',) 
    list_filter = ('status', 'created_at', 'pharmacy')
    search_fields = ('id', 'phone', 'full_name')
    inlines = [OrderItemInline]
    
    readonly_fields = ('user', 'full_name', 'phone', 'address_text', 'note', 
                       'delivery_lat', 'delivery_lng', 'distance_km',
                       'shipping_fee', 'total_product_price', 'final_total_price', 'created_at', 'pharmacy')

    def created_at_fmt(self, obj): return obj.created_at.strftime("%H:%M %d/%m")
    created_at_fmt.short_description = "Ngày đặt"

    def customer_info(self, obj): 
        return format_html("<b>{}</b><br><span style='color:#666'>{}</span>", obj.full_name, obj.phone)
    customer_info.short_description = "Khách hàng"

    def total_fmt(self, obj): return f"{obj.final_total_price:,} đ"
    total_fmt.short_description = "Tổng thu"

    def has_add_permission(self, request): return False

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser: return qs
        try: return qs.filter(pharmacy=request.user.staffprofile.pharmacy)
        except: return qs.none()

# --- 4. NHÂN VIÊN ---
@admin.register(StaffProfile)
class StaffProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'pharmacy_name')
    search_fields = ('user__username', 'pharmacy__name')

    def pharmacy_name(self, obj): return obj.pharmacy.name
    pharmacy_name.short_description = "Chi nhánh phụ trách"