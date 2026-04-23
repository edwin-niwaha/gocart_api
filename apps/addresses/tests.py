from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.addresses.models import CustomerAddress
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class AddressPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.staff = User.objects.create_user(email="address-staff@example.com", username="addressstaff", password="pass123456")
        self.staff.is_staff = True
        self.staff.save(update_fields=["is_staff"])
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)
        owner = User.objects.create_user(email="address-owner@example.com", username="addressowner", password="pass123456")
        CustomerAddress.objects.create(
            user=owner,
            street_name="Plot 2",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )

    def test_tenant_staff_cannot_list_all_customer_addresses(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.get("/api/v1/addresses/", HTTP_X_TENANT_SLUG=self.tenant.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)
