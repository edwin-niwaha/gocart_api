from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class UserEndpointPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Users Tenant", slug="users-tenant", is_active=True)
        self.other_tenant = Tenant.objects.create(name="Other Users Tenant", slug="other-users-tenant", is_active=True)
        self.user = User.objects.create_user(email="user@example.com", username="user", password="pass123456")
        self.other = User.objects.create_user(email="other@example.com", username="other", password="pass123456")
        self.staff = User.objects.create_user(email="staff-users@example.com", username="staffusers", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)
        TenantMembership.objects.create(tenant=self.tenant, user=self.other, role=TenantMembership.Role.STAFF)
        TenantMembership.objects.create(tenant=self.other_tenant, user=self.other, role=TenantMembership.Role.MANAGER)

    def test_regular_user_list_only_returns_self(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get("/api/v1/users/", HTTP_X_TENANT_SLUG=self.tenant.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], self.user.email)

    def test_tenant_staff_list_returns_tenant_members_only(self):
        self.client.force_authenticate(user=self.staff)

        response = self.client.get("/api/v1/users/", HTTP_X_TENANT_SLUG=self.tenant.slug)

        self.assertEqual(response.status_code, 200)
        emails = {item["email"] for item in response.data["results"]}
        self.assertEqual(emails, {self.staff.email, self.other.email})

        other_payload = next(item for item in response.data["results"] if item["email"] == self.other.email)
        membership_slugs = {item["tenant"]["slug"] for item in other_payload["tenant_memberships"]}
        self.assertEqual(membership_slugs, {self.tenant.slug})
