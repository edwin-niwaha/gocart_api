from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Tenant, TenantFeatureFlag, TenantMembership

User = get_user_model()


class TenantApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="JobellInc", slug="jobellinc", is_active=True, is_default=True)

    def test_current_tenant_endpoint_uses_header(self):
        alt = Tenant.objects.create(name="Alt", slug="alt", is_active=True)
        response = self.client.get("/api/v1/tenants/current/", HTTP_X_TENANT_SLUG=alt.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], "alt")

    def test_authenticated_user_membership_resolves_tenant(self):
        user = User.objects.create_user(email="member@example.com", username="member", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=user, role=TenantMembership.Role.TENANT_ADMIN)
        self.client.force_authenticate(user=user)
        response = self.client.get("/api/v1/tenants/current/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], self.tenant.slug)

    def test_tenant_admin_can_create_staff_membership(self):
        admin = User.objects.create_user(email="admin@example.com", username="admin", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        self.client.force_authenticate(user=admin)
        response = self.client.post(
            "/api/v1/tenants/current/memberships/",
            {
                "email": "staff@example.com",
                "username": "staff",
                "password": "pass123456",
                "role": TenantMembership.Role.STAFF,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(response.data["role"], TenantMembership.Role.STAFF)
        self.assertEqual(response.data["tenant"]["slug"], self.tenant.slug)

    def test_manager_cannot_create_membership(self):
        manager = User.objects.create_user(email="manager@example.com", username="manager", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=manager, role=TenantMembership.Role.MANAGER)
        self.client.force_authenticate(user=manager)
        response = self.client.post(
            "/api/v1/tenants/current/memberships/",
            {
                "email": "staff2@example.com",
                "username": "staff2",
                "password": "pass123456",
                "role": TenantMembership.Role.STAFF,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 403)

    def test_tenant_admin_cannot_assign_peer_role(self):
        admin = User.objects.create_user(email="owner@example.com", username="owner", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        self.client.force_authenticate(user=admin)
        response = self.client.post(
            "/api/v1/tenants/current/memberships/",
            {
                "email": "newadmin@example.com",
                "username": "newadmin",
                "password": "pass123456",
                "role": TenantMembership.Role.TENANT_ADMIN,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 400)

    def test_public_branding_and_settings_endpoints_return_current_tenant_config(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/tenants/current/branding/", HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["app_name"], self.tenant.name)

        response = self.client.get("/api/v1/tenants/current/settings/", HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["wishlist_enabled"])

    def test_tenant_admin_can_update_branding_and_feature_flags(self):
        admin = User.objects.create_user(email="brandadmin@example.com", username="brandadmin", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            "/api/v1/tenants/current/branding/",
            {"app_name": "Jobell Store", "primary_color": "#112233", "hero_title": "Shop faster"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["app_name"], "Jobell Store")

        response = self.client.patch(
            "/api/v1/tenants/current/settings/",
            {"support_chat_url": "https://example.com/help", "maintenance_mode": True},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data["maintenance_mode"])

        response = self.client.post(
            "/api/v1/tenants/current/feature-flags/",
            {"key": "flash-sales", "enabled": True, "description": "Enable seasonal flash sales"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(response.data["enabled"])
        self.assertTrue(TenantFeatureFlag.objects.filter(tenant=self.tenant, key="flash-sales", enabled=True).exists())

    def test_public_feature_flags_are_tenant_scoped(self):
        TenantFeatureFlag.objects.create(tenant=self.tenant, key="wishlist-experiments", enabled=True)
        alt = Tenant.objects.create(name="Alt", slug="alt", is_active=True)
        TenantFeatureFlag.objects.create(tenant=alt, key="wishlist-experiments", enabled=False)

        response = self.client.get("/api/v1/tenants/current/feature-flags/", HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 1)
        self.assertTrue(response.data[0]["enabled"])
