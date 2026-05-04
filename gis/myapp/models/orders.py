from datetime import timedelta
from django.contrib.auth.models import User
from django.db import models
from django.db.models import Q
from .accounts import UserProfile


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
    medicine = models.ForeignKey("Medicine", on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    @property
    def unit_price(self):
        return self.medicine.current_price

    @property
    def original_unit_price(self):
        return self.medicine.price

    @property
    def has_discount(self):
        return self.unit_price < self.original_unit_price

    @property
    def total_price(self):
        return self.unit_price * self.quantity

    class Meta:
        verbose_name = "San pham trong gio"
        verbose_name_plural = "San pham trong gio"
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(fields=["cart", "medicine"], name="unique_cart_medicine")
        ]


class Order(models.Model):
    STATUS_PENDING = "pending"
    STATUS_CONFIRMED = "confirmed"
    STATUS_PACKING = "packing"
    STATUS_SHIPPING = "shipping"
    STATUS_COMPLETED = "completed"
    STATUS_CANCELLED = "cancelled"
    STATUS_FAILED_DELIVERY = "failed_delivery"

    STATUS_CHOICES = (
        (STATUS_PENDING, "Chờ xử lý"),
        (STATUS_CONFIRMED, "Đã xác nhận"),
        (STATUS_PACKING, "Đang chuẩn bị"),
        (STATUS_SHIPPING, "Đang giao hàng"),
        (STATUS_COMPLETED, "Hoàn thành"),
        (STATUS_CANCELLED, "Đã hủy"),
        (STATUS_FAILED_DELIVERY, "Giao không thành công"),
    )
    INVENTORY_RELEASED_STATUSES = (STATUS_CANCELLED, STATUS_FAILED_DELIVERY)

    PAYMENT_COD = "cod"
    PAYMENT_MOMO = "momo"
    PAYMENT_BANK = "bank"
    PAYMENT_METHOD_CHOICES = (
        (PAYMENT_COD, "Thanh toán khi nhận hàng (COD)"),
        (PAYMENT_MOMO, "Vi MoMo"),
        (PAYMENT_BANK, "Chuyển khoản ngân hàng"),
    )

    PAYMENT_STATUS_COD_WAITING = "cod_waiting"
    PAYMENT_STATUS_AWAITING_TRANSFER = "awaiting_transfer"
    PAYMENT_STATUS_PAID = "paid"
    PAYMENT_STATUS_CHOICES = (
        (PAYMENT_STATUS_COD_WAITING, "Thu tiền khi giao hàng"),
        (PAYMENT_STATUS_AWAITING_TRANSFER, "Chờ xác nhận thanh toán"),
        (PAYMENT_STATUS_PAID, "Đã thanh toán"),
    )

    PRESCRIPTION_STATUS_NOT_REQUIRED = "not_required"
    PRESCRIPTION_STATUS_PENDING = "pending"
    PRESCRIPTION_STATUS_APPROVED = "approved"
    PRESCRIPTION_STATUS_REJECTED = "rejected"
    PRESCRIPTION_STATUS_CHOICES = (
        (PRESCRIPTION_STATUS_NOT_REQUIRED, "Không yêu cầu đơn thuốc"),
        (PRESCRIPTION_STATUS_PENDING, "Chờ duyệt đơn thuốc"),
        (PRESCRIPTION_STATUS_APPROVED, "Đơn thuốc hợp lệ"),
        (PRESCRIPTION_STATUS_REJECTED, "Từ chối đơn thuốc"),
    )

    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, verbose_name="Tai khoan khach")
    full_name = models.CharField(max_length=100, verbose_name="Nguoi nhan")
    phone = models.CharField(max_length=20, verbose_name="SDT lien he")
    address_text = models.CharField(max_length=255, verbose_name="Dia chi giao")
    note = models.TextField(verbose_name="Ghi chu cua khach", blank=True, null=True)

    delivery_lat = models.FloatField(verbose_name="Vi do", null=True, blank=True)
    delivery_lng = models.FloatField(verbose_name="Kinh do", null=True, blank=True)

    pharmacy = models.ForeignKey("Pharmacy", on_delete=models.SET_NULL, null=True, verbose_name="Chi nhanh xu ly")

    distance_km = models.FloatField(default=0, verbose_name="Khoang cach (km)")
    shipping_fee = models.IntegerField(default=0, verbose_name="Phi ship")
    total_product_price = models.IntegerField(default=0, verbose_name="Tien hang")
    final_total_price = models.IntegerField(default=0, verbose_name="Tong thanh toan")
    customer_tier_name = models.CharField(max_length=40, blank=True, default="", verbose_name="Hang khach hang luc dat")
    customer_tier_discount_percent = models.PositiveSmallIntegerField(default=0, verbose_name="Muc giam theo hang KH (%)")
    customer_tier_discount_total = models.PositiveIntegerField(default=0, verbose_name="Tong tien giam theo hang KH")

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_COD,
        verbose_name="Phuong thuc thanh toan",
    )
    payment_status = models.CharField(
        max_length=30,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_COD_WAITING,
        verbose_name="Trang thai thanh toan",
    )
    payment_reference = models.CharField(max_length=120, blank=True, default="", verbose_name="Ma tham chieu thanh toan")
    payment_proof_image = models.ImageField(upload_to="payments/proofs/", blank=True, null=True, verbose_name="Anh chung tu thanh toan")
    payment_note = models.TextField(blank=True, default="", verbose_name="Ghi chu thanh toan")
    payment_confirmed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payment_confirmed_orders",
        verbose_name="Nhan vien xac nhan thanh toan",
    )
    payment_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian xac nhan thanh toan")

    prescription_status = models.CharField(
        max_length=20,
        choices=PRESCRIPTION_STATUS_CHOICES,
        default=PRESCRIPTION_STATUS_NOT_REQUIRED,
        verbose_name="Trang thai don thuoc",
    )
    prescription_proof_image = models.ImageField(upload_to="prescriptions/proofs/", blank=True, null=True, verbose_name="Anh don thuoc")
    prescription_note = models.TextField(blank=True, default="", verbose_name="Ghi chu don thuoc cua khach")
    prescription_admin_note = models.TextField(blank=True, default="", verbose_name="Ghi chu duyet don thuoc")
    prescription_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="prescription_reviewed_orders",
        verbose_name="Nhan vien duyet don thuoc",
    )
    prescription_reviewed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian duyet don thuoc")

    invoice_requested = models.BooleanField(default=False, verbose_name="Khach yeu cau xuat hoa don")
    invoice_code = models.CharField(max_length=40, blank=True, default="", db_index=True, verbose_name="Ma hoa don")
    invoice_staff_name = models.CharField(max_length=150, blank=True, default="", verbose_name="Nhan vien lap hoa don")

    estimated_delivery_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian giao du kien")
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian hoan thanh")
    received_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Khach xac nhan da nhan")
    auto_completed_at = models.DateTimeField(null=True, blank=True, verbose_name="Tu dong hoan thanh")
    cancelled_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian huy")

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING, verbose_name="Trang thai don")
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Thoi gian dat")

    def __str__(self):
        return f"Don #{self.id} - {self.full_name}"

    @property
    def order_code(self):
        if self.pk:
            return f"DH{self.pk:06d}"
        return "DH-TAM"

    @property
    def resolved_invoice_code(self):
        return self.invoice_code or (f"HD{self.created_at.strftime('%Y%m%d')}-{self.pk:06d}" if self.pk and self.created_at else "HD-TAM")

    @property
    def resolved_payment_reference(self):
        return self.payment_reference or self.order_code

    @property
    def auto_complete_deadline_at(self):
        base_dt = self.estimated_delivery_at or self.created_at
        if not base_dt:
            return None
        return base_dt + timedelta(days=5)

    @property
    def can_customer_cancel(self):
        return self.status == self.STATUS_PENDING

    @property
    def can_customer_confirm_received(self):
        return self.status == self.STATUS_SHIPPING

    @property
    def can_request_return_refund(self):
        return self.status == self.STATUS_COMPLETED

    @property
    def requires_payment_confirmation(self):
        return self.payment_method in {self.PAYMENT_BANK, self.PAYMENT_MOMO}

    @property
    def can_upload_payment_proof(self):
        return (
            self.requires_payment_confirmation
            and self.payment_status == self.PAYMENT_STATUS_AWAITING_TRANSFER
            and self.status not in set(self.INVENTORY_RELEASED_STATUSES)
        )

    @property
    def requires_prescription_review(self):
        return self.prescription_status != self.PRESCRIPTION_STATUS_NOT_REQUIRED

    @property
    def prescription_is_approved(self):
        return self.prescription_status in {
            self.PRESCRIPTION_STATUS_NOT_REQUIRED,
            self.PRESCRIPTION_STATUS_APPROVED,
        }

    @property
    def has_customer_tier_discount(self):
        return self.customer_tier_discount_percent > 0 and self.customer_tier_discount_total > 0

    @property
    def product_subtotal_before_tier_discount(self):
        return int(self.total_product_price or 0) + int(self.customer_tier_discount_total or 0)

    @property
    def resolved_invoice_staff_name(self):
        staff_name = (self.invoice_staff_name or "").strip()
        if staff_name:
            normalized_staff_name = staff_name.casefold()
            matched_profile = UserProfile.objects.select_related("user").filter(
                Q(full_name__iexact=staff_name) | Q(user__username__iexact=staff_name)
            ).order_by("id").first()
            if matched_profile:
                candidate = (matched_profile.full_name or "").strip()
                if not candidate and matched_profile.user:
                    candidate = (
                        matched_profile.user.get_full_name().strip()
                        or matched_profile.user.first_name.strip()
                        or matched_profile.user.username
                    )
                if candidate:
                    return candidate
            if normalized_staff_name != "nhân viên quầy thuốc":
                return staff_name

        pharmacy = getattr(self, "pharmacy", None)
        if pharmacy:
            profile = pharmacy.managed_staff_profiles.select_related("user").order_by("id").first()
            if profile:
                candidate = (profile.full_name or "").strip()
                if not candidate and profile.user:
                    candidate = (profile.user.get_full_name() or profile.user.first_name or "").strip()
                if candidate:
                    return candidate
        return staff_name or "Nhân viên quầy thuốc"

    class Meta:
        verbose_name = "Don hang"
        verbose_name_plural = "Xu ly Don hang"
        ordering = ["-created_at", "-id"]


class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    medicine = models.ForeignKey("Medicine", on_delete=models.SET_NULL, null=True)
    medicine_name = models.CharField(max_length=200)
    price = models.IntegerField()
    quantity = models.PositiveIntegerField()

    @property
    def line_total(self):
        return self.price * self.quantity

    class Meta:
        verbose_name = "Chi tiet san pham"
        verbose_name_plural = "Chi tiet san pham"


class ReturnRefundRequest(models.Model):
    STATUS_PROCESSING = "processing"
    STATUS_APPROVED = "approved_refund"
    STATUS_REJECTED = "rejected_refund"

    STATUS_CHOICES = (
        (STATUS_PROCESSING, "Đang xử lý"),
        (STATUS_APPROVED, "Chấp nhận hoàn tiền"),
        (STATUS_REJECTED, "Từ chối hoàn tiền"),
    )

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="return_request")
    reason = models.TextField(verbose_name="Ly do tra hang / hoan tien")
    bank_account_number = models.CharField(max_length=80, blank=True, default="", verbose_name="So tai khoan ngan hang")
    momo_account_number = models.CharField(max_length=80, blank=True, default="", verbose_name="So tai khoan MoMo")
    contact_email = models.EmailField(blank=True, default="", verbose_name="Email lien he")
    contact_phone = models.CharField(max_length=20, blank=True, default="", verbose_name="So dien thoai lien he")
    bill_image = models.ImageField(upload_to="returns/bills/", blank=True, null=True, verbose_name="Anh bill / hoa don")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PROCESSING, verbose_name="Trang thai xu ly")
    admin_note = models.TextField(blank=True, default="", verbose_name="Ghi chu xu ly noi bo")
    processed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="processed_return_requests",
        verbose_name="Nhan vien xu ly",
    )
    processed_at = models.DateTimeField(null=True, blank=True, verbose_name="Thoi gian xu ly")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Yeu cau tra hang / hoan tien - Don #{self.order_id}"

    @property
    def proof_image_count(self):
        return self.evidences.count()

    @property
    def is_finalized(self):
        return self.status in {self.STATUS_APPROVED, self.STATUS_REJECTED}

    @property
    def processed_by_display_name(self):
        user = getattr(self, "processed_by", None)
        if not user:
            return ""
        profile = getattr(user, "profile", None)
        if profile and (profile.full_name or "").strip():
            return profile.full_name.strip()
        return (user.get_full_name() or user.first_name or user.username).strip()

    class Meta:
        verbose_name = "Yeu cau tra hang / hoan tien"
        verbose_name_plural = "Yeu cau tra hang / hoan tien"
        ordering = ["-created_at", "-id"]


class OrderPrescriptionProof(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="prescription_proof_images")
    image = models.ImageField(upload_to="prescriptions/proofs/", verbose_name="Anh don thuoc")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anh don thuoc #{self.pk} - Don #{self.order_id}"

    class Meta:
        verbose_name = "Anh don thuoc cua don hang"
        verbose_name_plural = "Anh don thuoc cua don hang"
        ordering = ["id"]


class ReturnRefundEvidence(models.Model):
    request = models.ForeignKey(ReturnRefundRequest, on_delete=models.CASCADE, related_name="evidences")
    image = models.ImageField(upload_to="returns/evidences/", verbose_name="Anh chung minh")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Anh chung minh #{self.pk} - Don #{self.request.order_id}"

    class Meta:
        verbose_name = "Anh chung minh tra hang"
        verbose_name_plural = "Anh chung minh tra hang"
        ordering = ["id"]

