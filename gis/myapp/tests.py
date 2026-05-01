import re
from datetime import timedelta
from django.contrib.auth.hashers import make_password
from django.contrib.auth.models import User
from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .forms import AccountProfileForm, AboutPageContentForm, CheckoutForm, MedicineAdminForm, OrderStatusUpdateForm, PaymentProofUploadForm, PharmacyAdminForm, ProfilePasswordChangeForm, ReturnRefundRequestForm
from .models import AccountOtpChallenge, AboutPageContent, Cart, CartItem, Medicine, MedicineLot, MedicineReview, NewsArticle, Order, OrderItem, Pharmacy, ReturnRefundRequest, UserProfile, fold_text_for_match
from .tools.calculations import estimate_road_distance_km
from .tools.geocode import _build_search_variants, _clean_reverse_display_name, _format_nominatim_reverse_display_name
from .tools.routing import DeliveryRoutingService
from .views import get_or_create_medicine_for_import


class GeocodeAddressFormattingTest(SimpleTestCase):
    def test_reverse_geocode_removes_intermediate_admin_but_keeps_parent_city(self):
        payload = {
            'lat': '10.8050',
            'lon': '106.6250',
            'display_name': 'Hẻm 163 Nguyễn Phúc Chu, Phường Tân Sơn, Thành phố Thủ Đức, Thành phố Hồ Chí Minh, 71509, Việt Nam',
            'address': {
                'road': 'Hẻm 163 Nguyễn Phúc Chu',
                'suburb': 'Phường Tân Sơn',
                'city_district': 'Thành phố Thủ Đức',
                'state': 'Thành phố Hồ Chí Minh',
                'postcode': '71509',
                'country': 'Việt Nam',
            },
        }

        self.assertEqual(
            _format_nominatim_reverse_display_name(payload, 'fallback'),
            'Hẻm 163 Nguyễn Phúc Chu, Phường Tân Sơn, Thành phố Hồ Chí Minh, 71509, Việt Nam',
        )

    def test_reverse_geocode_keeps_non_central_city_hierarchy(self):
        payload = {
            'lat': '10.9500',
            'lon': '106.8200',
            'display_name': 'Đường Đồng Khởi, Thành phố Biên Hòa, Đồng Nai, Việt Nam',
            'address': {
                'road': 'Đường Đồng Khởi',
                'city': 'Thành phố Biên Hòa',
                'state': 'Đồng Nai',
                'country': 'Việt Nam',
            },
        }

        self.assertEqual(
            _format_nominatim_reverse_display_name(payload, 'fallback'),
            'Đường Đồng Khởi, Thành phố Biên Hòa, Đồng Nai, Việt Nam',
        )

    def test_raw_reverse_display_name_uses_generic_central_city_cleanup(self):
        self.assertEqual(
            _clean_reverse_display_name(
                'Hẻm 163 Nguyễn Phúc Chu, Phường Tân Sơn, Thành phố Thủ Đức, Thành phố Hồ Chí Minh, 71509, Việt Nam',
                'fallback',
                lat=10.8050,
                lng=106.6250,
            ),
            'Hẻm 163 Nguyễn Phúc Chu, Phường Tân Sơn, Thành phố Hồ Chí Minh, 71509, Việt Nam',
        )

    def test_search_variants_follow_map_bias_instead_of_hard_coding_hcm(self):
        hanoi_variants = _build_search_variants('Lê Lợi', bias_lat=21.0285, bias_lng=105.8542)
        no_bias_variants = _build_search_variants('Lê Lợi')

        self.assertTrue(hanoi_variants[0].endswith('Hà Nội, Việt Nam'))
        self.assertFalse(any('Hồ Chí Minh' in item for item in no_bias_variants))


class DeliveryRoutingServiceTest(TestCase):
    def test_estimate_route_returns_expected_keys(self):
        service = DeliveryRoutingService()
        result = service.estimate_route(10.77, 106.69, 10.78, 106.70)

        self.assertIn('routes', result)
        self.assertTrue(len(result['routes']) > 0)
        self.assertIn('distance_km', result['routes'][0])
        self.assertIn('shipping_fee_value', result['routes'][0])

    def test_estimate_road_distance_uses_factor_for_each_delivery_mode(self):
        self.assertAlmostEqual(estimate_road_distance_km(10, 'motorbike'), 12.0)
        self.assertAlmostEqual(estimate_road_distance_km(10, 'car'), 13.0)
        self.assertAlmostEqual(estimate_road_distance_km(10, 'walking'), 10.5)
        self.assertAlmostEqual(estimate_road_distance_km(10, 'unknown-mode'), 12.0)


class PharmacyAvailabilityTest(TestCase):
    def test_has_available_medicines_property(self):
        pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc A',
            address='123 Test',
            phone='0900000000',
            opening_hours='8:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.assertFalse(pharmacy.has_available_medicines)

        Medicine.objects.create(
            pharmacy=pharmacy,
            name='Paracetamol',
            price=10000,
            quantity=5,
        )
        self.assertTrue(pharmacy.has_available_medicines)


class InventoryWorkflowTest(TestCase):
    TINY_PNG = (
        b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
    )

    def setUp(self):
        self.pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Test',
            address='123 Đường Test',
            phone='0900000001',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.customer = User.objects.create_user(
            username='customer_test',
            password='Test@123456',
        )

    def test_checkout_reduces_stock_by_order_quantity(self):
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Paracetamol 500mg',
            price=12000,
            quantity=10,
            unit='Hộp',
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, medicine=medicine, quantity=3)

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('checkout'),
            {
                'full_name': 'Khách Test',
                'phone': '0900000002',
                'address_text': '1 Nguyễn Huệ, Quận 1',
                'note': '',
                'delivery_lat': '10.7750',
                'delivery_lng': '106.7000',
                'pharmacy_id': str(self.pharmacy.pk),
            },
        )

        self.assertEqual(response.status_code, 302)
        medicine.refresh_from_db()
        self.assertEqual(medicine.quantity, 7)
        self.assertTrue(Order.objects.exists())
        self.assertEqual(OrderItem.objects.get().quantity, 3)

    def test_cancelling_order_restores_stock_when_status_changes(self):
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Vitamin C',
            price=50000,
            quantity=7,
            unit='Hộp',
        )
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Test',
            phone='0900000002',
            address_text='1 Nguyễn Huệ, Quận 1',
            pharmacy=self.pharmacy,
            total_product_price=150000,
            final_total_price=165000,
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(
            order=order,
            medicine=medicine,
            medicine_name=medicine.name,
            price=medicine.price,
            quantity=3,
        )

        order.status = Order.STATUS_CANCELLED
        order.save()

        medicine.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertEqual(medicine.quantity, 10)

    def test_staff_can_cancel_order_in_custom_admin_and_stock_is_restored(self):
        staff_user = User.objects.create_user(
            username='staff_test',
            password='Test@123456',
            is_staff=True,
        )
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Omega 3',
            price=90000,
            quantity=5,
            unit='Hộp',
        )
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Test',
            phone='0900000002',
            address_text='1 Nguyễn Huệ, Quận 1',
            pharmacy=self.pharmacy,
            total_product_price=180000,
            final_total_price=195000,
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(
            order=order,
            medicine=medicine,
            medicine_name=medicine.name,
            price=medicine.price,
            quantity=2,
        )

        self.client.force_login(staff_user)
        response = self.client.post(
            reverse('custom_admin_order_detail', args=[order.pk]),
            {
                'pharmacy': str(self.pharmacy.pk),
                'status': Order.STATUS_CANCELLED,
            },
        )

        self.assertEqual(response.status_code, 302)
        medicine.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertEqual(medicine.quantity, 7)

    def test_admin_cannot_change_order_branch_after_items_are_allocated(self):
        other_pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc khác',
            address='456 Đường Khác',
            phone='0900000098',
            opening_hours='08:00 - 22:00',
            lat=10.78,
            lng=106.7,
        )
        admin_user = User.objects.create_superuser(
            username='branch_admin',
            password='Test@123456',
            email='branch_admin@example.com',
        )
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Kẽm bổ sung',
            price=50000,
            quantity=8,
            unit='Hộp',
        )
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Test',
            phone='0900000002',
            address_text='1 Nguyễn Huệ, Quận 1',
            pharmacy=self.pharmacy,
            total_product_price=100000,
            final_total_price=115000,
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(
            order=order,
            medicine=medicine,
            medicine_name=medicine.name,
            price=medicine.price,
            quantity=2,
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse('custom_admin_order_detail', args=[order.pk]),
            {
                'pharmacy': str(other_pharmacy.pk),
                'status': Order.STATUS_PENDING,
                'payment_status': Order.PAYMENT_STATUS_COD_WAITING,
                'prescription_status': Order.PRESCRIPTION_STATUS_NOT_REQUIRED,
            },
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.pharmacy, self.pharmacy)

    def test_failed_delivery_restores_stock(self):
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Men vi sinh',
            price=70000,
            quantity=4,
            unit='Hộp',
        )
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Test',
            phone='0900000002',
            address_text='1 Nguyễn Huệ, Quận 1',
            pharmacy=self.pharmacy,
            total_product_price=140000,
            final_total_price=155000,
            status=Order.STATUS_SHIPPING,
        )
        OrderItem.objects.create(
            order=order,
            medicine=medicine,
            medicine_name=medicine.name,
            price=medicine.price,
            quantity=2,
        )

        order.status = Order.STATUS_FAILED_DELIVERY
        order.save()

        medicine.refresh_from_db()
        self.assertEqual(medicine.quantity, 6)

    def test_checkout_requires_prescription_image_for_prescription_medicine(self):
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Kháng sinh kê đơn',
            price=120000,
            quantity=10,
            unit='Hộp',
            prescription_required=True,
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, medicine=medicine, quantity=1)

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('checkout'),
            {
                'full_name': 'Khách Test',
                'phone': '0900000002',
                'address_text': '1 Nguyễn Huệ, Quận 1',
                'note': '',
                'delivery_lat': '10.7750',
                'delivery_lng': '106.7000',
                'pharmacy_id': str(self.pharmacy.pk),
                'payment_method': Order.PAYMENT_COD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())

    def test_checkout_stores_prescription_image_and_marks_pending_review(self):
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Thuốc kê đơn',
            price=90000,
            quantity=5,
            unit='Hộp',
            prescription_required=True,
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, medicine=medicine, quantity=1)

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('checkout'),
            {
                'full_name': 'Khách Test',
                'phone': '0900000002',
                'address_text': '1 Nguyễn Huệ, Quận 1',
                'note': '',
                'delivery_lat': '10.7750',
                'delivery_lng': '106.7000',
                'pharmacy_id': str(self.pharmacy.pk),
                'payment_method': Order.PAYMENT_COD,
                'prescription_proof_image': SimpleUploadedFile('toa.png', __import__('base64').b64decode(self.TINY_PNG), content_type='image/png'),
            },
        )

        self.assertEqual(response.status_code, 302)
        order = Order.objects.get()
        self.assertEqual(order.prescription_status, Order.PRESCRIPTION_STATUS_PENDING)
        self.assertTrue(order.prescription_proof_image)

    def test_checkout_rechecks_prescription_requirement_on_allocated_branch_medicine(self):
        other_pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc kê đơn',
            address='789 Đường Toa',
            phone='0900000088',
            opening_hours='08:00 - 22:00',
            lat=10.78,
            lng=106.7,
        )
        cart_medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Thuốc đồng bộ lệch',
            price=90000,
            quantity=0,
            unit='Hộp',
            manufacturer='GIS',
            origin='Việt Nam',
            prescription_required=False,
        )
        Medicine.objects.create(
            pharmacy=other_pharmacy,
            name='Thuốc đồng bộ lệch',
            price=90000,
            quantity=5,
            unit='Hộp',
            manufacturer='GIS',
            origin='Việt Nam',
            prescription_required=True,
        )
        cart = Cart.objects.create(user=self.customer)
        CartItem.objects.create(cart=cart, medicine=cart_medicine, quantity=1)

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('checkout'),
            {
                'full_name': 'Khách Test',
                'phone': '0900000002',
                'address_text': '1 Nguyễn Huệ, Quận 1',
                'note': '',
                'delivery_lat': '10.7750',
                'delivery_lng': '106.7000',
                'pharmacy_id': str(other_pharmacy.pk),
                'payment_method': Order.PAYMENT_COD,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertFalse(Order.objects.exists())


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PaymentExperienceTest(TestCase):
    TINY_PNG = (
        b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
    )

    def setUp(self):
        self.pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Thanh Toán',
            address='456 Đường QR',
            phone='0900000009',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.customer = User.objects.create_user(
            username='payment_user',
            password='Test@123456',
            email='payment_user@example.com',
        )

    def test_payment_preview_api_returns_qr_data_for_bank(self):
        response = self.client.get(
            reverse('payment_preview_api'),
            {
                'payment_method': 'bank',
                'amount': '125000',
                'pharmacy_id': str(self.pharmacy.pk),
                'reference': 'DH000001-0604',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['show_qr'])
        self.assertTrue(
            payload['qr_image'].startswith('data:image')
            or payload['qr_image'].startswith('https://img.vietqr.io/')
            or payload['qr_image'].startswith('/static/images/')
        )
        self.assertEqual(payload['amount_value'], 125000)

    @override_settings(
        PAYMENT_BANK_QR_IMAGE_URL='images/payment-bank-qr.png',
        PAYMENT_MOMO_QR_IMAGE_URL='images/payment-momo-qr.png',
    )
    def test_payment_preview_api_uses_configured_custom_qr_images(self):
        bank_response = self.client.get(
            reverse('payment_preview_api'),
            {
                'payment_method': 'bank',
                'amount': '125000',
                'pharmacy_id': str(self.pharmacy.pk),
                'reference': 'DH000001-0604',
            },
        )
        self.assertEqual(bank_response.status_code, 200)
        self.assertEqual(bank_response.json()['qr_image'], '/static/images/payment-bank-qr.png')

        momo_response = self.client.get(
            reverse('payment_preview_api'),
            {
                'payment_method': 'momo',
                'amount': '125000',
                'pharmacy_id': str(self.pharmacy.pk),
                'reference': 'DH000001-0604',
            },
        )
        self.assertEqual(momo_response.status_code, 200)
        self.assertEqual(momo_response.json()['qr_image'], '/static/images/payment-momo-qr.png')

    def test_invoice_view_is_available_for_order_owner(self):
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Invoice',
            phone='0900000010',
            address_text='789 Đường In Hóa Đơn',
            pharmacy=self.pharmacy,
            total_product_price=150000,
            shipping_fee=15000,
            final_total_price=165000,
            payment_method=Order.PAYMENT_BANK,
            payment_status=Order.PAYMENT_STATUS_AWAITING_TRANSFER,
            payment_reference='DH000123-0604',
            invoice_code='HD20260406-000123',
            invoice_staff_name='Nhân viên Test',
        )
        OrderItem.objects.create(
            order=order,
            medicine=None,
            medicine_name='Paracetamol',
            price=150000,
            quantity=1,
        )

        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_invoice_view', args=[order.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'HÓA ĐƠN BÁN HÀNG')
        self.assertContains(response, 'Nhân viên Test')

    def test_customer_can_upload_transfer_payment_proof(self):
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Payment',
            phone='0900000010',
            address_text='1 Nguyễn Huệ',
            pharmacy=self.pharmacy,
            total_product_price=125000,
            shipping_fee=15000,
            final_total_price=140000,
            payment_method=Order.PAYMENT_BANK,
            payment_status=Order.PAYMENT_STATUS_AWAITING_TRANSFER,
            payment_reference='DH000321-0604',
        )

        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('upload_payment_proof', args=[order.pk]),
            {
                'payment_proof_image': SimpleUploadedFile('proof.png', __import__('base64').b64decode(self.TINY_PNG), content_type='image/png'),
                'payment_note': 'Đã chuyển khoản lúc 09:00',
            },
        )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertTrue(order.payment_proof_image)
        self.assertEqual(order.payment_note, 'Đã chuyển khoản lúc 09:00')
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_AWAITING_TRANSFER)

    def test_payment_proof_rejects_renamed_non_image_file(self):
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Payment',
            phone='0900000010',
            address_text='1 Nguyễn Huệ',
            pharmacy=self.pharmacy,
            total_product_price=125000,
            shipping_fee=15000,
            final_total_price=140000,
            payment_method=Order.PAYMENT_BANK,
            payment_status=Order.PAYMENT_STATUS_AWAITING_TRANSFER,
            payment_reference='DH000322-0604',
        )

        form = PaymentProofUploadForm(
            data={'payment_note': 'File giả ảnh'},
            files={
                'payment_proof_image': SimpleUploadedFile(
                    'proof.png',
                    b'not a real image',
                    content_type='image/png',
                )
            },
            instance=order,
        )

        self.assertFalse(form.is_valid())
        self.assertIn('payment_proof_image', form.errors)

    def test_admin_cannot_ship_transfer_order_before_payment_confirmed(self):
        admin_user = User.objects.create_user(username='payment_admin', password='Test@123456', is_staff=True)
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Payment',
            phone='0900000010',
            address_text='1 Nguyễn Huệ',
            pharmacy=self.pharmacy,
            total_product_price=125000,
            shipping_fee=15000,
            final_total_price=140000,
            payment_method=Order.PAYMENT_BANK,
            payment_status=Order.PAYMENT_STATUS_AWAITING_TRANSFER,
            status=Order.STATUS_PENDING,
        )

        self.client.force_login(admin_user)
        response = self.client.post(
            reverse('custom_admin_order_detail', args=[order.pk]),
            {
                'pharmacy': str(self.pharmacy.pk),
                'status': Order.STATUS_SHIPPING,
                'payment_status': Order.PAYMENT_STATUS_AWAITING_TRANSFER,
                'prescription_status': Order.PRESCRIPTION_STATUS_NOT_REQUIRED,
            },
        )

        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)

    def test_admin_can_confirm_transfer_payment_then_move_order_forward(self):
        admin_user = User.objects.create_user(username='payment_admin_ok', password='Test@123456', is_staff=True)
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách Payment',
            phone='0900000010',
            address_text='1 Nguyễn Huệ',
            pharmacy=self.pharmacy,
            total_product_price=125000,
            shipping_fee=15000,
            final_total_price=140000,
            payment_method=Order.PAYMENT_BANK,
            payment_status=Order.PAYMENT_STATUS_AWAITING_TRANSFER,
            status=Order.STATUS_PENDING,
        )

        self.client.force_login(admin_user)
        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('custom_admin_order_detail', args=[order.pk]),
                {
                    'pharmacy': str(self.pharmacy.pk),
                    'status': Order.STATUS_PENDING,
                    'payment_status': Order.PAYMENT_STATUS_PAID,
                    'prescription_status': Order.PRESCRIPTION_STATUS_NOT_REQUIRED,
                },
            )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_PENDING)
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertIsNotNone(order.payment_confirmed_at)
        self.assertEqual(order.payment_confirmed_by, admin_user)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.order_code, mail.outbox[0].subject)
        self.assertIn('thanh toán', mail.outbox[0].subject.lower())

        for next_status in (Order.STATUS_CONFIRMED, Order.STATUS_PACKING, Order.STATUS_SHIPPING):
            response = self.client.post(
                reverse('custom_admin_order_detail', args=[order.pk]),
                {
                    'pharmacy': str(self.pharmacy.pk),
                    'status': next_status,
                    'payment_status': Order.PAYMENT_STATUS_PAID,
                    'prescription_status': Order.PRESCRIPTION_STATUS_NOT_REQUIRED,
                },
            )
            self.assertEqual(response.status_code, 302)
            order.refresh_from_db()
            self.assertEqual(order.status, next_status)


class OrderPostPurchaseWorkflowTest(TestCase):
    TINY_PNG = (
        b'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4//8/AAX+Av4N70a4AAAAAElFTkSuQmCC'
    )


    def setUp(self):
        self.pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Hậu mãi',
            address='12 Nguyễn Trãi',
            phone='0900000099',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.customer = User.objects.create_user(username='buyer_case', password='Test@123456', email='buyer@example.com')
        self.medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Thuốc A',
            price=100000,
            quantity=20,
            unit='Hộp',
        )

    def create_order(self, status=Order.STATUS_PENDING, payment_method=Order.PAYMENT_COD, estimated_delivery_at=None):
        order = Order.objects.create(
            user=self.customer,
            full_name='Khách hàng A',
            phone='0900000011',
            address_text='1 Nguyễn Huệ',
            pharmacy=self.pharmacy,
            total_product_price=200000,
            shipping_fee=15000,
            final_total_price=215000,
            payment_method=payment_method,
            payment_status=Order.PAYMENT_STATUS_COD_WAITING if payment_method == Order.PAYMENT_COD else Order.PAYMENT_STATUS_AWAITING_TRANSFER,
            status=status,
            estimated_delivery_at=estimated_delivery_at,
        )
        OrderItem.objects.create(order=order, medicine=self.medicine, medicine_name=self.medicine.name, price=self.medicine.price, quantity=2)
        return order

    def test_customer_can_cancel_pending_order(self):
        order = self.create_order(status=Order.STATUS_PENDING)
        self.client.force_login(self.customer)
        response = self.client.post(reverse('cancel_order', args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CANCELLED)
        self.assertIsNotNone(order.cancelled_at)

    def test_customer_confirm_received_marks_order_completed(self):
        order = self.create_order(status=Order.STATUS_SHIPPING)
        self.client.force_login(self.customer)
        response = self.client.post(reverse('confirm_order_received', args=[order.pk]))
        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        self.assertEqual(order.payment_status, Order.PAYMENT_STATUS_PAID)
        self.assertIsNotNone(order.received_confirmed_at)

    def test_order_history_auto_completes_overdue_shipping_order(self):
        order = self.create_order(
            status=Order.STATUS_SHIPPING,
            estimated_delivery_at=timezone.now() - timedelta(days=6),
        )
        self.client.force_login(self.customer)
        response = self.client.get(reverse('order_history'))
        self.assertEqual(response.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        self.assertIsNotNone(order.auto_completed_at)

    def test_order_history_is_paginated_three_orders_per_page(self):
        for _ in range(5):
            self.create_order(status=Order.STATUS_PENDING)

        self.client.force_login(self.customer)

        first_page = self.client.get(reverse('order_history'))
        self.assertEqual(first_page.status_code, 200)
        self.assertEqual(len(first_page.context['orders']), 3)
        self.assertEqual(first_page.context['page_obj'].number, 1)
        self.assertEqual(first_page.context['page_obj'].paginator.num_pages, 2)

        second_page = self.client.get(reverse('order_history'), {'page': 2})
        self.assertEqual(second_page.status_code, 200)
        self.assertEqual(len(second_page.context['orders']), 2)
        self.assertEqual(second_page.context['page_obj'].number, 2)

    def test_completed_order_can_create_return_request(self):
        order = self.create_order(status=Order.STATUS_COMPLETED)
        self.client.force_login(self.customer)
        response = self.client.post(
            reverse('return_request', args=[order.pk]),
            {
                'reason': 'Giao sai sản phẩm',
                'bank_account_number': '123456789',
                'momo_account_number': '',
                'contact_email': 'buyer@example.com',
                'contact_phone': '0900000011',
                'bill_image': SimpleUploadedFile('bill.png', __import__('base64').b64decode(self.TINY_PNG), content_type='image/png'),
                'proof_images': [SimpleUploadedFile('proof1.png', __import__('base64').b64decode(self.TINY_PNG), content_type='image/png')],
            },
        )
        self.assertEqual(response.status_code, 302)
        request_obj = ReturnRefundRequest.objects.get(order=order)
        self.assertEqual(request_obj.status, ReturnRefundRequest.STATUS_PROCESSING)
        self.assertEqual(request_obj.evidences.count(), 1)


class ReviewUpdateFlagTest(TestCase):
    def test_review_update_flag_only_true_after_real_update(self):
        pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Review',
            address='456 Test',
            phone='0900000022',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        medicine = Medicine.objects.create(pharmacy=pharmacy, name='Thuốc Review', price=10000, quantity=5)
        user = User.objects.create_user(username='review_user', password='Test@123456')
        review = MedicineReview.objects.create(user=user, medicine=medicine, rating=5, comment='Tốt')
        self.assertFalse(review.was_updated_by_user)
        MedicineReview.objects.filter(pk=review.pk).update(is_edited=True)
        review.refresh_from_db()
        self.assertTrue(review.was_updated_by_user)


class MedicineCatalogSyncWorkflowTest(TestCase):
    def setUp(self):
        self.branch_a = Pharmacy.objects.create(
            name='Nha thuoc A',
            address='1 Duong A',
            phone='0900000200',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.branch_b = Pharmacy.objects.create(
            name='Nha thuoc B',
            address='2 Duong B',
            phone='0900000201',
            opening_hours='08:00 - 22:00',
            lat=10.78,
            lng=106.7,
        )
        self.admin_user = User.objects.create_superuser(
            username='catalog_admin',
            password='Test@123456',
            email='catalog_admin@example.com',
        )

    def test_fold_text_for_match_normalizes_vietnamese_d_character(self):
        self.assertEqual(fold_text_for_match('điều trị'), 'dieu tri')
        self.assertEqual(
            fold_text_for_match('Oresol bù nước'),
            fold_text_for_match('Oresol bu nuoc'),
        )

    def test_medicine_admin_form_syncs_shared_fields_across_catalog_group(self):
        medicine_a = Medicine.objects.create(
            pharmacy=self.branch_a,
            name='Oresol bu nuoc',
            category='Tieu hoa',
            unit='Goi',
            manufacturer='DHG Pharma',
            origin='Viet Nam',
            price=12000,
            quantity=0,
            description='Mo ta cu',
            usage='Cong dung cu',
            ingredients='Thanh phan cu',
            dosage='Lieu cu',
            prescription_required=False,
        )
        medicine_b = Medicine.objects.create(
            pharmacy=self.branch_b,
            name='Oresol bù nước',
            category='',
            unit='Goi',
            manufacturer='DHG Pharma',
            origin='',
            price=10000,
            quantity=0,
            description='',
            usage='',
            ingredients='',
            dosage='',
            prescription_required=False,
        )

        form = MedicineAdminForm(
            data={
                'pharmacy': str(self.branch_a.pk),
                'name': 'Oresol bù nước chuẩn',
                'category': 'Tieu hoa',
                'unit': 'Goi',
                'manufacturer': 'DHG Pharma',
                'origin': 'Việt Nam',
                'price': '15000',
                'gallery_urls': '',
                'description': 'Bù nước và điện giải cho cơ thể.',
                'usage': 'Hỗ trợ bù nước nhanh.',
                'ingredients': 'Glucose, natri clorid.',
                'dosage': 'Dùng theo hướng dẫn trên gói.',
                'prescription_required': 'on',
            },
            instance=medicine_a,
            admin_user=self.admin_user,
        )

        self.assertTrue(form.is_valid(), form.errors.as_json())
        saved = form.save()
        medicine_b.refresh_from_db()

        self.assertEqual(saved.name, 'Oresol bù nước chuẩn')
        self.assertEqual(medicine_b.name, 'Oresol bù nước chuẩn')
        self.assertEqual(medicine_b.origin, 'Việt Nam')
        self.assertEqual(medicine_b.price, 15000)
        self.assertEqual(medicine_b.description, 'Bù nước và điện giải cho cơ thể.')
        self.assertEqual(medicine_b.usage, 'Hỗ trợ bù nước nhanh.')
        self.assertTrue(medicine_b.prescription_required)

    def test_import_reuses_existing_medicine_when_excel_name_is_without_accents(self):
        existing_medicine = Medicine.objects.create(
            pharmacy=self.branch_a,
            name='Oresol bù nước',
            category='Tieu hoa',
            unit='Goi',
            manufacturer='DHG Pharma',
            origin='Việt Nam',
            price=12000,
            quantity=0,
        )

        medicine, was_created = get_or_create_medicine_for_import(
            self.branch_a,
            {
                'medicine_name': 'Oresol bu nuoc',
                'manufacturer': 'DHG Pharma',
                'unit': 'Goi',
                'sale_price': '18000',
            },
            row_number=2,
        )

        self.assertFalse(was_created)
        self.assertEqual(medicine.pk, existing_medicine.pk)
        self.assertEqual(medicine.name, 'Oresol bù nước')


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class RegistrationEmailActivationTest(TestCase):
    def test_register_sends_activation_email_and_activates_after_link_click(self):
        response = self.client.post(
            reverse('register'),
            {
                'username': 'new_customer',
                'email': 'new_customer@example.com',
                'password': 'Test@123456',
                'confirm_password': 'Test@123456',
            },
        )

        self.assertRedirects(response, reverse('login'))
        user = User.objects.get(username='new_customer')
        self.assertFalse(user.is_active)
        self.assertTrue(UserProfile.objects.filter(user=user).exists())
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Xác nhận đăng ký tài khoản', mail.outbox[0].subject)
        activation_match = re.search(r'http://testserver(?P<path>/register/activate/[^\s]+)', mail.outbox[0].body)
        self.assertIsNotNone(activation_match)

        inactive_login_response = self.client.post(
            reverse('login'),
            {'username': 'new_customer', 'password': 'Test@123456'},
        )
        self.assertEqual(inactive_login_response.status_code, 200)
        self.assertContains(inactive_login_response, 'chưa xác nhận email')

        activation_response = self.client.get(activation_match.group('path'))
        self.assertRedirects(activation_response, reverse('login'))
        user.refresh_from_db()
        self.assertTrue(user.is_active)

        login_response = self.client.post(
            reverse('login'),
            {'username': 'new_customer', 'password': 'Test@123456'},
        )
        self.assertRedirects(login_response, reverse('home'))

    def test_register_rejects_duplicate_email_even_when_username_is_different(self):
        User.objects.create_user(
            username='existing_customer',
            email='duplicate@example.com',
            password='Test@123456',
        )

        response = self.client.post(
            reverse('register'),
            {
                'username': 'other_customer',
                'email': 'duplicate@example.com',
                'password': 'Test@123456',
                'confirm_password': 'Test@123456',
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Email này đã được dùng để đăng ký tài khoản.')
        self.assertFalse(User.objects.filter(username='other_customer').exists())
        self.assertEqual(len(mail.outbox), 0)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class EmailNotificationWorkflowTest(TestCase):
    def setUp(self):
        self.pharmacy = Pharmacy.objects.create(
            name='Nha thuoc Email',
            address='99 Duong Email',
            phone='0900000100',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.customer = User.objects.create_user(
            username='email_customer',
            password='Test@123456',
            email='email_customer@example.com',
        )
        self.admin_user = User.objects.create_superuser(
            username='email_admin',
            password='Test@123456',
            email='admin@example.com',
        )

    def create_order(self, status=Order.STATUS_PENDING):
        return Order.objects.create(
            user=self.customer,
            full_name='Khach Email',
            phone='0900000101',
            address_text='123 Duong Email',
            pharmacy=self.pharmacy,
            total_product_price=150000,
            shipping_fee=15000,
            final_total_price=165000,
            payment_method=Order.PAYMENT_COD,
            payment_status=Order.PAYMENT_STATUS_COD_WAITING,
            status=status,
        )

    def test_admin_order_status_change_sends_email(self):
        order = self.create_order(status=Order.STATUS_PENDING)
        self.client.force_login(self.admin_user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('custom_admin_order_detail', args=[order.pk]),
                {
                    'pharmacy': str(self.pharmacy.pk),
                    'status': Order.STATUS_CONFIRMED,
                },
            )

        self.assertEqual(response.status_code, 302)
        order.refresh_from_db()
        self.assertEqual(order.status, Order.STATUS_CONFIRMED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.order_code, mail.outbox[0].subject)
        self.assertIn('Đã xác nhận', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.customer.email])

    def test_return_request_status_change_sends_email(self):
        order = self.create_order(status=Order.STATUS_COMPLETED)
        request_obj = ReturnRefundRequest.objects.create(
            order=order,
            reason='Giao sai sản phẩm',
            contact_email='fallback@example.com',
            contact_phone='0900000101',
            status=ReturnRefundRequest.STATUS_PROCESSING,
        )
        self.client.force_login(self.admin_user)

        with self.captureOnCommitCallbacks(execute=True):
            response = self.client.post(
                reverse('custom_admin_return_request_detail', args=[request_obj.pk]),
                {
                    'status': ReturnRefundRequest.STATUS_APPROVED,
                    'admin_note': 'Đã duyệt hoàn tiền cho khách.',
                },
            )

        self.assertEqual(response.status_code, 302)
        request_obj.refresh_from_db()
        order.refresh_from_db()
        self.assertEqual(request_obj.status, ReturnRefundRequest.STATUS_APPROVED)
        self.assertEqual(order.status, Order.STATUS_COMPLETED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(order.order_code, mail.outbox[0].subject)
        self.assertIn('Đã duyệt hoàn tiền cho khách.', mail.outbox[0].body)
        self.assertEqual(mail.outbox[0].to, [self.customer.email])

    def test_username_recovery_email_includes_username(self):
        response = self.client.post(
            f"{reverse('password_reset')}?recovery=username",
            {'email': self.customer.email},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('Gửi lại tên đăng nhập', mail.outbox[0].subject)
        self.assertIn(self.customer.username, mail.outbox[0].body)


class RichContentPresentationTest(TestCase):
    def setUp(self):
        self.pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Mô tả',
            address='99 Đường Mẫu',
            phone='0909999999',
            opening_hours='08:00 - 22:00',
            desc='<p><strong>Chi nhánh trung tâm</strong> với khu vực tư vấn riêng.</p>',
            lat=10.77,
            lng=106.69,
        )
        self.medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Cetirizin 10mg',
            price=25000,
            quantity=12,
            unit='Hộp',
            description='<p>Thuốc giảm triệu chứng viêm mũi dị ứng và mề đay.</p>',
            usage='<p>Công dụng cũ</p>',
            ingredients='<p>Thành phần cũ</p>',
            dosage='<p>Cách dùng cũ</p>',
        )

    def test_pharmacy_detail_shows_description_block(self):
        response = self.client.get(reverse('pharmacy_detail', args=[self.pharmacy.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('pharmacy-description-panel', content)
        self.assertIn('Chi nhánh trung tâm', content)
        self.assertLess(content.index('Trạng thái phục vụ'), content.index('pharmacy-description-panel'))

    def test_medicine_detail_separates_description_and_removes_legacy_sections(self):
        response = self.client.get(reverse('medicine_detail', args=[self.medicine.pk]))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('medicine-description-panel', content)
        self.assertIn('Thuốc giảm triệu chứng viêm mũi dị ứng và mề đay.', content)
        self.assertIn('buy-panel--compact', content)
        self.assertIn('Thêm vào giỏ hàng', content)
        self.assertIn('Mua ngay', content)
        self.assertNotIn('<h3><i class="fas fa-briefcase-medical"></i> Công dụng</h3>', content)
        self.assertNotIn('<h3><i class="fas fa-flask"></i> Thành phần</h3>', content)
        self.assertNotIn('<h3><i class="fas fa-notes-medical"></i> Cách dùng</h3>', content)


class RichEditorAdminExperienceTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='admin_editor',
            email='admin@example.com',
            password='Test@123456',
        )
        self.pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Editor',
            address='12 Đường Admin',
            phone='0901231231',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )

    def test_admin_forms_expose_rich_editor_attributes(self):
        pharmacy_form = PharmacyAdminForm()
        medicine_form = MedicineAdminForm(admin_user=self.superuser)

        self.assertEqual(pharmacy_form.fields['desc'].widget.attrs.get('data-rich-editor'), '1')
        self.assertEqual(medicine_form.fields['description'].widget.attrs.get('data-rich-editor'), '1')
        self.assertEqual(medicine_form.fields['usage'].widget.attrs.get('data-rich-editor'), '1')
        self.assertFalse(pharmacy_form.fields['desc'].help_text)
        self.assertFalse(medicine_form.fields['description'].help_text)

    def test_custom_admin_create_pages_render_visible_wysiwyg_toolbar_and_hide_specialized_block(self):
        self.client.force_login(self.superuser)

        pharmacy_response = self.client.get(reverse('custom_admin_create', args=['pharmacy']))
        medicine_response = self.client.get(reverse('custom_admin_create', args=['medicine']))

        self.assertEqual(pharmacy_response.status_code, 200)
        self.assertEqual(medicine_response.status_code, 200)
        self.assertContains(pharmacy_response, 'data-rich-editor-root')
        self.assertContains(pharmacy_response, 'data-editor-image-width')
        self.assertContains(pharmacy_response, 'data-editor-image-reset')
        self.assertContains(medicine_response, 'data-rich-editor-root')
        self.assertContains(medicine_response, 'data-editor-image-align=\"center\"')
        self.assertContains(medicine_response, 'data-editor-source-toggle')
        self.assertNotContains(medicine_response, 'Thông tin chuyên môn')


class AboutPageRefreshTest(TestCase):
    def test_about_page_introduces_website_products_benefits_and_branches(self):
        pharmacy = Pharmacy.objects.create(
            name='Quan 5 Branch',
            address='51 Nguyen Trai, Quan 5',
            phone='0901111111',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        Medicine.objects.create(
            pharmacy=pharmacy,
            name='Vitamin C 500mg',
            price=30000,
            quantity=10,
            unit='Hộp',
            category='Vitamin',
            product_type='medicine',
        )

        response = self.client.get(reverse('about'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('About GIS Pharma', content)
        self.assertIn('story + value + CTA', content)
        self.assertIn('about-value-grid', content)
        self.assertIn('about-branch-grid', content)
        self.assertIn('Quan 5 Branch', content)
        self.assertIn('Vitamin', content)
        self.assertEqual(response.context['product_type_summary']['medicine'], 1)
        self.assertEqual(response.context['pharmacy_total'], 1)


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class AdminEnhancementRegressionTest(TestCase):
    def setUp(self):
        self.superuser = User.objects.create_superuser(
            username='root_admin',
            email='root@example.com',
            password='Test@123456',
        )
        self.staff = User.objects.create_user(
            username='staff_perm',
            email='staff@example.com',
            password='Test@123456',
            is_staff=True,
        )
        self.pharmacy = Pharmacy.objects.create(
            name='Nhà thuốc Trung tâm',
            address='1 Đường Chính',
            phone='0902222222',
            opening_hours='08:00 - 22:00',
            lat=10.77,
            lng=106.69,
        )
        self.profile = UserProfile.objects.create(user=self.superuser, full_name='Root Admin', phone='0901111222')
        UserProfile.objects.create(user=self.staff, full_name='Nhân viên', phone='0903333444', managed_pharmacy=self.pharmacy)

    def test_admin_form_pages_render_rich_editor_and_locked_coordinates(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('custom_admin_create', args=['pharmacy']))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('data-rich-editor-root', content)
        self.assertIn('data-editor-image-width', content)
        self.assertIn('data-editor-image-reset', content)
        self.assertIn('readonly', content)
        self.assertIn('height: 520px', content)

        medicine_response = self.client.get(reverse('custom_admin_create', args=['medicine']))
        self.assertEqual(medicine_response.status_code, 200)
        self.assertContains(medicine_response, 'data-editor-image-align=\"center\"')
        self.assertContains(medicine_response, 'data-editor-source-toggle')
        self.assertNotContains(medicine_response, 'Thông tin chuyên môn')

    def test_home_page_admin_renders_management_formsets(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('custom_admin_home_page'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Quan ly trang chu')
        self.assertContains(response, 'hero_slides-TOTAL_FORMS')
        self.assertContains(response, 'category_items-TOTAL_FORMS')
        self.assertContains(response, 'commitment_items-TOTAL_FORMS')

    def test_news_create_page_and_purchase_import_page_render_new_tools(self):
        self.client.force_login(self.superuser)

        news_response = self.client.get(reverse('custom_admin_create', args=['news']))
        self.assertEqual(news_response.status_code, 200)
        self.assertContains(news_response, 'data-rich-editor-root')
        self.assertContains(news_response, 'id_cover_image-live-preview')

        import_response = self.client.get(reverse('custom_admin_create', args=['purchase_import']))
        self.assertEqual(import_response.status_code, 200)
        self.assertContains(import_response, 'purchase-import-preview-data')
        self.assertContains(import_response, 'excel-new-products-trigger')
        self.assertContains(import_response, 'new-products-modal')

    def test_home_hero_slides_link_to_about_page(self):
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertIn('hero-splide__link', content)
        self.assertEqual(content.count('class="hero-splide__link"'), 3)
        self.assertIn('data-interval="4000"', content)

    def test_about_page_admin_updates_public_about_content(self):
        self.client.force_login(self.superuser)
        content = AboutPageContent.get_solo()

        admin_response = self.client.get(reverse('custom_admin_about_page'))
        self.assertEqual(admin_response.status_code, 200)
        self.assertContains(admin_response, 'Quản lý nội dung trang Giới thiệu')

        form = AboutPageContentForm(instance=content)
        data = {field_name: getattr(content, field_name) for field_name in form.fields}
        data['hero_title'] = 'Trang giới thiệu đang lấy nội dung từ trang quản lý'
        data['story_title'] = 'Câu chuyện đã được chỉnh trong admin'
        data['cta_primary_label'] = 'Xem catalog đã chỉnh'

        response = self.client.post(reverse('custom_admin_about_page'), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('custom_admin_about_page'))

        public_response = self.client.get(reverse('about'))
        self.assertEqual(public_response.status_code, 200)
        self.assertContains(public_response, 'Trang giới thiệu đang lấy nội dung từ trang quản lý')
        self.assertContains(public_response, 'Câu chuyện đã được chỉnh trong admin')
        self.assertContains(public_response, 'Xem catalog đã chỉnh')

    def test_news_article_generates_slug_and_public_page(self):
        article = NewsArticle.objects.create(
            title='Thong bao he thong GIS Pharma',
            summary='Tom tat bai viet',
            content='<p>Noi dung bai viet</p>',
            is_published=True,
            created_by=self.superuser,
            updated_by=self.superuser,
        )

        self.assertTrue(article.slug)
        self.assertIsNotNone(article.published_at)

        response = self.client.get(reverse('news_detail', args=[article.slug]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Thong bao he thong GIS Pharma')
        self.assertContains(response, 'Noi dung bai viet')

    def test_permissions_center_is_grouped_and_review_insights_removed(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('custom_admin_permissions_center'), {'user': self.staff.pk})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nhóm 1 · Tổng quan và vận hành chính')
        self.assertContains(response, 'Nhóm 2 · Sản phẩm, kho và báo cáo')
        self.assertContains(response, 'Nhóm 3 · Tài khoản và phân quyền')
        self.assertNotContains(response, 'Phân tích đánh giá')

    def test_review_insights_route_redirects_back_to_reports(self):
        self.client.force_login(self.superuser)
        response = self.client.get(reverse('custom_admin_review_insights'))
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('custom_admin_reports'))

    def test_home_featured_pharmacies_use_sellable_lot_inventory(self):
        medicine = Medicine.objects.create(
            pharmacy=self.pharmacy,
            name='Thuốc còn lô',
            price=15000,
            quantity=0,
            unit='Hộp',
        )
        MedicineLot.objects.create(
            medicine=medicine,
            pharmacy=self.pharmacy,
            source_label='LOT-AVAILABLE',
            received_quantity=10,
            remaining_quantity=10,
            expiry_date=timezone.localdate() + timedelta(days=90),
        )
        response = self.client.get(reverse('home'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nhà thuốc Trung tâm')

    def test_inventory_alert_center_paginates_three_rows_each_section_and_keeps_panel_open(self):
        self.client.force_login(self.superuser)
        for index in range(6):
            med = Medicine.objects.create(
                pharmacy=self.pharmacy,
                name=f'Hết hạn {index}',
                price=10000 + index,
                quantity=1,
            )
            MedicineLot.objects.create(
                medicine=med,
                pharmacy=self.pharmacy,
                source_label=f'EXP-{index}',
                received_quantity=5,
                remaining_quantity=5,
                expiry_date=timezone.localdate() - timedelta(days=index + 1),
            )
        for index in range(6):
            med = Medicine.objects.create(
                pharmacy=self.pharmacy,
                name=f'Cận hạn {index}',
                price=20000 + index,
                quantity=1,
            )
            MedicineLot.objects.create(
                medicine=med,
                pharmacy=self.pharmacy,
                source_label=f'WRN-{index}',
                received_quantity=5,
                remaining_quantity=5,
                expiry_date=timezone.localdate() + timedelta(days=20 + index),
            )

        response = self.client.get(reverse('custom_admin_list', args=['inventory_lot']))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode('utf-8')
        self.assertEqual(content.count('Đi tới phiếu xử lý'), 6)
        self.assertIn('Hiển thị tối đa 3 dòng mỗi trang', content)
        self.assertIn('inventory_alert_open=1', content)
        self.assertIn('expired_page=2', content)
        self.assertIn('warning_page=2', content)

        next_page_response = self.client.get(reverse('custom_admin_list', args=['inventory_lot']), {'expired_page': 2, 'inventory_alert_open': 1})
        self.assertEqual(next_page_response.status_code, 200)
        self.assertContains(next_page_response, 'admin-alert-center is-open')

    def test_phone_validation_uses_vietnamese_messages(self):
        account_form = AccountProfileForm(
            data={'full_name': 'A', 'email': 'a@example.com', 'phone': '12345'},
            user=self.superuser,
            profile=self.profile,
            is_customer=False,
        )
        self.assertFalse(account_form.is_valid())
        self.assertIn('Số điện thoại phải gồm đúng 10 chữ số', account_form.errors['phone'][0])

        checkout_form = CheckoutForm(data={
            'full_name': 'Khách A',
            'phone': '09123',
            'address_text': '12 Đường A',
            'payment_method': Order.PAYMENT_COD,
        })
        self.assertFalse(checkout_form.is_valid())
        self.assertIn('Số điện thoại phải gồm đúng 10 chữ số', checkout_form.errors['phone'][0])

    def test_password_change_blocks_reuse_and_sends_notification_email(self):
        self.client.force_login(self.superuser)
        response = self.client.post(reverse('account'), {
            'form_action': 'change_password',
            'old_password': 'Test@123456',
            'new_password1': 'Test@123456',
            'new_password2': 'Test@123456',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Mật khẩu mới không được trùng với mật khẩu đang dùng trước đó.')
        self.assertEqual(len(mail.outbox), 0)

        response = self.client.post(reverse('account'), {
            'form_action': 'change_password',
            'old_password': 'Test@123456',
            'new_password1': 'MoiMatKhau@123',
            'new_password2': 'MoiMatKhau@123',
        })
        self.assertEqual(response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('thay đổi mật khẩu', mail.outbox[0].subject.lower())

    def test_password_recovery_also_blocks_reuse_and_sends_notification_email(self):
        challenge = AccountOtpChallenge.objects.create(
            user=self.superuser,
            purpose=AccountOtpChallenge.PURPOSE_PASSWORD_RESET,
            email=self.superuser.email,
            otp_hash=make_password('123456'),
            username_snapshot=self.superuser.username,
            expires_at=timezone.now() + timedelta(minutes=10),
        )

        invalid_response = self.client.post(reverse('account_recovery_verify', args=[challenge.public_token]), {
            'otp_code': '123456',
            'new_password1': 'Test@123456',
            'new_password2': 'Test@123456',
        })
        self.assertEqual(invalid_response.status_code, 200)
        self.assertContains(invalid_response, 'Mật khẩu mới không được trùng với mật khẩu đang dùng trước đó.')
        self.assertEqual(len(mail.outbox), 0)

        challenge.otp_hash = make_password('654321')
        challenge.consumed_at = None
        challenge.attempts = 0
        challenge.expires_at = timezone.now() + timedelta(minutes=10)
        challenge.save(update_fields=['otp_hash', 'consumed_at', 'attempts', 'expires_at', 'updated_at'])

        valid_response = self.client.post(reverse('account_recovery_verify', args=[challenge.public_token]), {
            'otp_code': '654321',
            'new_password1': 'MatKhauMoiKhac@456',
            'new_password2': 'MatKhauMoiKhac@456',
        })
        self.assertEqual(valid_response.status_code, 302)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn('thay đổi mật khẩu', mail.outbox[0].subject.lower())
