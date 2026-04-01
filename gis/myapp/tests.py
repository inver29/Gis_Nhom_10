from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from .models import Cart, CartItem, Medicine, Order, OrderItem, Pharmacy
from .tool import DeliveryRoutingService


class DeliveryRoutingServiceTest(TestCase):
    def test_estimate_route_returns_expected_keys(self):
        service = DeliveryRoutingService()
        result = service.estimate_route(10.77, 106.69, 10.78, 106.70)

        self.assertIn('routes', result)
        self.assertTrue(len(result['routes']) > 0)
        self.assertIn('distance_km', result['routes'][0])
        self.assertIn('shipping_fee_value', result['routes'][0])


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
