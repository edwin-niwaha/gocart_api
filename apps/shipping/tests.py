from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.addresses.models import CustomerAddress
from apps.orders.models import Order
from apps.shipping.models import Shipment, ShippingMethod
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class ShipmentPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        self.staff_a = User.objects.create_user(email="ship-staff@example.com", username="shipstaff", password="pass123456")
        self.staff_a.is_staff = True
        self.staff_a.save(update_fields=["is_staff"])
        TenantMembership.objects.create(tenant=self.tenant_a, user=self.staff_a, role=TenantMembership.Role.STAFF)
        self.customer_b = User.objects.create_user(email="ship-buyer-b@example.com", username="shipbuyerb", password="pass123456")
        self.address_b = CustomerAddress.objects.create(
            user=self.customer_b,
            street_name="Plot B",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        self.order_b = Order.objects.create(
            user=self.customer_b,
            tenant=self.tenant_b,
            address=self.address_b,
            status=Order.Status.PAID,
            slug="tenant-b-order",
        )
        self.shipping_method = ShippingMethod.objects.create(
            name="Door delivery",
            fee="5000.00",
            estimated_days=2,
            is_active=True,
        )

    def test_tenant_staff_cannot_list_other_tenant_shipments(self):
        Shipment.objects.create(
            order=self.order_b,
            address=self.address_b,
            shipping_method=self.shipping_method,
            shipping_fee=self.shipping_method.fee,
        )
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get("/api/v1/shipments/", HTTP_X_TENANT_SLUG=self.tenant_a.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_tenant_staff_cannot_create_shipment_for_other_tenant_order(self):
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.post(
            "/api/v1/shipments/",
            {
                "order": self.order_b.id,
                "address": self.address_b.id,
                "shipping_method": self.shipping_method.id,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Shipment.objects.exists())
