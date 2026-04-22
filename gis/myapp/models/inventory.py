from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone


class PurchaseImportBatch(models.Model):
    pharmacy = models.ForeignKey("Pharmacy", on_delete=models.CASCADE, related_name="purchase_import_batches", verbose_name="Chi nhanh nhap hang")
    invoice_code = models.CharField(max_length=80, blank=True, default="", db_index=True, verbose_name="Ma hoa don nhap")
    source_file = models.FileField(upload_to="imports/excel/", verbose_name="File Excel nhap hang")
    receipt_pdf = models.FileField(upload_to="imports/receipts/", blank=True, null=True, verbose_name="Phieu nhap PDF")
    imported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="purchase_import_batches",
        verbose_name="Nguoi phu trach nhap hang",
    )
    imported_by_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Ho ten nguoi phu trach")
    imported_by_email = models.EmailField(blank=True, default="", verbose_name="Email nguoi phu trach")
    imported_by_role = models.CharField(max_length=120, blank=True, default="", verbose_name="Chuc vu nguoi phu trach")
    note = models.TextField(blank=True, default="", verbose_name="Ghi chu")
    total_lines = models.PositiveIntegerField(default=0, verbose_name="So dong hop le")
    total_quantity = models.PositiveIntegerField(default=0, verbose_name="Tong so luong nhap")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian nhap")

    def __str__(self):
        return self.invoice_code or f"NHAP-{self.pk or 'TAM'}"

    @property
    def resolved_invoice_code(self):
        if self.invoice_code:
            return self.invoice_code
        if self.pk and self.created_at:
            return f"NHAP{self.created_at.strftime('%Y%m%d')}-{self.pk:05d}"
        return "NHAP-TAM"

    @property
    def resolved_imported_by_name(self):
        raw_name = (self.imported_by_name or "").strip()
        user = getattr(self, "imported_by", None)
        if user:
            profile = getattr(user, "profile", None)
            if profile and (profile.full_name or "").strip():
                return profile.full_name.strip()
            candidate = (user.get_full_name() or user.first_name or "").strip()
            if candidate:
                return candidate
            if raw_name and raw_name.casefold() != user.username.casefold():
                return raw_name
            return user.username
        return raw_name or "Nhân viên nhập hàng"

    class Meta:
        verbose_name = "Phieu nhap hang"
        verbose_name_plural = "Nhap hang bang Excel"
        ordering = ["-created_at", "-id"]


class PurchaseImportItem(models.Model):
    batch = models.ForeignKey(PurchaseImportBatch, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey("Medicine", on_delete=models.SET_NULL, null=True, blank=True, related_name="purchase_import_items")
    medicine_name = models.CharField(max_length=200, verbose_name="Ten thuoc")
    manufacturer = models.CharField(max_length=150, blank=True, default="", verbose_name="Nha san xuat")
    unit = models.CharField(max_length=50, blank=True, default="", verbose_name="Don vi tinh")
    previous_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton truoc khi nhap")
    imported_quantity = models.PositiveIntegerField(default=0, verbose_name="So luong nhap")
    new_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton sau khi nhap")
    import_price = models.PositiveIntegerField(default=0, verbose_name="Gia nhap")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Han su dung nhap vao")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chu dong")

    def __str__(self):
        return f"{self.medicine_name} - batch #{self.batch_id}"

    class Meta:
        verbose_name = "Chi tiet nhap hang"
        verbose_name_plural = "Chi tiet nhap hang"
        ordering = ["id"]


class StockExportBatch(models.Model):
    EXPORT_SCOPE_STANDARD = "standard"
    EXPORT_SCOPE_RECONCILE = "reconcile"
    EXPORT_SCOPE_EXPIRED = "expired"
    EXPORT_SCOPE_CHOICES = (
        (EXPORT_SCOPE_STANDARD, "Xuất nội bộ / chuyển kho"),
        (EXPORT_SCOPE_RECONCILE, "Đối soát tồn vật lý"),
        (EXPORT_SCOPE_EXPIRED, "Xử lý hàng hết hạn"),
    )

    pharmacy = models.ForeignKey(
        "Pharmacy",
        on_delete=models.CASCADE,
        related_name="stock_export_batches",
        verbose_name="Chi nhanh xuat kho",
    )
    export_scope = models.CharField(
        max_length=20,
        choices=EXPORT_SCOPE_CHOICES,
        default=EXPORT_SCOPE_STANDARD,
        verbose_name="Loai phieu xuat",
    )
    export_code = models.CharField(max_length=80, blank=True, default="", db_index=True, verbose_name="Ma phieu xuat")
    receipt_pdf = models.FileField(upload_to="exports/receipts/", blank=True, null=True, verbose_name="Phieu xuat PDF")
    exported_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="stock_export_batches",
        verbose_name="Nguoi lap phieu xuat",
    )
    exported_by_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Ho ten nguoi lap phieu")
    exported_by_email = models.EmailField(blank=True, default="", verbose_name="Email nguoi lap phieu")
    exported_by_role = models.CharField(max_length=120, blank=True, default="", verbose_name="Chuc vu nguoi lap phieu")
    destination_name = models.CharField(max_length=180, blank=True, default="", verbose_name="Noi nhan / muc dich xuat")
    note = models.TextField(blank=True, default="", verbose_name="Ghi chu")
    total_lines = models.PositiveIntegerField(default=0, verbose_name="So dong xuat")
    total_quantity = models.PositiveIntegerField(default=0, verbose_name="Tong so luong xuat")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian xuat")

    def __str__(self):
        return self.export_code or f"XUAT-{self.pk or 'TAM'}"

    @property
    def resolved_export_code(self):
        if self.export_code:
            return self.export_code
        if self.pk and self.created_at:
            return f"XUAT{self.created_at.strftime('%Y%m%d')}-{self.pk:05d}"
        return "XUAT-TAM"

    @property
    def resolved_exported_by_name(self):
        raw_name = (self.exported_by_name or "").strip()
        user = getattr(self, "exported_by", None)
        if user:
            profile = getattr(user, "profile", None)
            if profile and (profile.full_name or "").strip():
                return profile.full_name.strip()
            candidate = (user.get_full_name() or user.first_name or "").strip()
            if candidate:
                return candidate
            if raw_name and raw_name.casefold() != user.username.casefold():
                return raw_name
            return user.username
        return raw_name or "Nhân viên xuất kho"

    class Meta:
        verbose_name = "Phieu xuat kho"
        verbose_name_plural = "Phieu xuat kho"
        ordering = ["-created_at", "-id"]


class StockExportItem(models.Model):
    batch = models.ForeignKey(StockExportBatch, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey("Medicine", on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_export_items")
    medicine_name = models.CharField(max_length=200, verbose_name="Ten san pham")
    manufacturer = models.CharField(max_length=150, blank=True, default="", verbose_name="Nha san xuat")
    unit = models.CharField(max_length=50, blank=True, default="", verbose_name="Don vi tinh")
    previous_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton truoc khi xuat")
    exported_quantity = models.PositiveIntegerField(default=0, verbose_name="So luong xuat")
    remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Ton sau khi xuat")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chu dong")

    def __str__(self):
        return f"{self.medicine_name} - export #{self.batch_id}"

    class Meta:
        verbose_name = "Chi tiet xuat kho"
        verbose_name_plural = "Chi tiet xuat kho"
        ordering = ["id"]


class MedicineLot(models.Model):
    SOURCE_IMPORT = "purchase_import"
    SOURCE_MANUAL = "manual_adjustment"
    SOURCE_RETURN = "return_restore"

    SOURCE_CHOICES = (
        (SOURCE_IMPORT, "Nhập hàng"),
        (SOURCE_MANUAL, "Điều chỉnh tay"),
        (SOURCE_RETURN, "Hoàn kho từ đơn hàng"),
    )

    medicine = models.ForeignKey("Medicine", on_delete=models.CASCADE, related_name="lots", verbose_name="Thuốc")
    pharmacy = models.ForeignKey("Pharmacy", on_delete=models.CASCADE, related_name="medicine_lots", verbose_name="Chi nhánh")
    purchase_batch = models.ForeignKey(
        PurchaseImportBatch,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicine_lots",
        verbose_name="Phiếu nhập nguồn",
    )
    purchase_item = models.ForeignKey(
        PurchaseImportItem,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="medicine_lots",
        verbose_name="Dòng nhập nguồn",
    )
    source_type = models.CharField(max_length=30, choices=SOURCE_CHOICES, default=SOURCE_IMPORT, verbose_name="Nguồn tạo lô")
    source_label = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn nguồn")
    import_price = models.PositiveIntegerField(default=0, verbose_name="Giá nhập")
    expiry_date = models.DateField(null=True, blank=True, verbose_name="Hạn sử dụng")
    received_quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng nhập lô")
    remaining_quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng còn lại")
    note = models.CharField(max_length=255, blank=True, default="", verbose_name="Ghi chú")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        base = self.source_label or f"Lô #{self.pk}"
        return f"{self.medicine.name} - {base}"

    @property
    def is_expired(self):
        return bool(self.expiry_date and self.expiry_date < timezone.localdate())

    @property
    def is_sellable(self):
        if self.remaining_quantity <= 0:
            return False
        if self.expiry_date and self.expiry_date < timezone.localdate():
            return False
        return True

    @property
    def expiry_days_remaining(self):
        if not self.expiry_date:
            return None
        return (self.expiry_date - timezone.localdate()).days

    class Meta:
        verbose_name = "Lô tồn kho thuốc"
        verbose_name_plural = "Lô tồn kho thuốc"
        ordering = ["expiry_date", "created_at", "id"]
        indexes = [
            models.Index(fields=["medicine", "expiry_date"], name="idx_medlot_med_exp"),
            models.Index(fields=["pharmacy", "expiry_date"], name="idx_medlot_pharm_exp"),
        ]


class OrderItemLotAllocation(models.Model):
    order_item = models.ForeignKey('OrderItem', on_delete=models.CASCADE, related_name="lot_allocations", verbose_name="Dòng đơn hàng")
    lot = models.ForeignKey(MedicineLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="order_allocations", verbose_name="Lô thuốc")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng phân bổ")
    lot_expiry_date = models.DateField(null=True, blank=True, verbose_name="HSD snapshot")
    lot_import_price = models.PositiveIntegerField(default=0, verbose_name="Giá nhập snapshot")
    lot_source_label = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn lô snapshot")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alloc order_item #{self.order_item_id} - lot #{self.lot_id or 'NA'}"

    class Meta:
        verbose_name = "Phân bổ lô cho dòng đơn"
        verbose_name_plural = "Phân bổ lô cho dòng đơn"
        ordering = ["id"]


class StockExportLotAllocation(models.Model):
    export_item = models.ForeignKey(StockExportItem, on_delete=models.CASCADE, related_name="lot_allocations", verbose_name="Dòng phiếu xuất")
    lot = models.ForeignKey(MedicineLot, on_delete=models.SET_NULL, null=True, blank=True, related_name="stock_export_allocations", verbose_name="Lô thuốc")
    quantity = models.PositiveIntegerField(default=0, verbose_name="Số lượng phân bổ")
    lot_expiry_date = models.DateField(null=True, blank=True, verbose_name="HSD snapshot")
    lot_import_price = models.PositiveIntegerField(default=0, verbose_name="Giá nhập snapshot")
    lot_source_label = models.CharField(max_length=120, blank=True, default="", verbose_name="Nhãn lô snapshot")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Alloc export_item #{self.export_item_id} - lot #{self.lot_id or 'NA'}"

    class Meta:
        verbose_name = "Phân bổ lô cho phiếu xuất"
        verbose_name_plural = "Phân bổ lô cho phiếu xuất"
        ordering = ["id"]

