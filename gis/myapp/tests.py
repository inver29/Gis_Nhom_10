from django.test import TestCase

from .models import Medicine, Pharmacy
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