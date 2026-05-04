from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from .models import Tenant, TenantFeatureFlag, TenantMembership

User = get_user_model()


class TenantApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="GoCart", slug="GoCart", is_active=True, is_default=True)

    def test_current_tenant_endpoint_uses_header(self):
        alt = Tenant.objects.create(name="Alt", slug="alt", is_active=True)
        response = self.client.get("/api/v1/tenants/current/", HTTP_X_TENANT_SLUG=alt.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["slug"], "alt")

    def test_invalid_explicit_tenant_header_fails_closed(self):
        response = self.client.get("/api/v1/tenants/current/", HTTP_X_TENANT_SLUG="missing-tenant")

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json()["detail"], "Tenant not found.")
        self.assertEqual(response.json()["code"], "tenant_not_found")

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
        self.assertEqual(response.data["email"], "staff@example.com")
        self.assertEqual(response.data["status"], "active")

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
            {"app_name": "GoCart", "primary_color": "#112233", "hero_title": "Shop faster"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["app_name"], "GoCart")

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

    def test_membership_list_supports_search_and_status_filter(self):
        admin = User.objects.create_user(email="searchadmin@example.com", username="searchadmin", password="pass123456")
        active_user = User.objects.create_user(email="alice@example.com", username="alice", password="pass123456", first_name="Alice")
        inactive_user = User.objects.create_user(email="bob@example.com", username="bobby", password="pass123456", first_name="Bob")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        TenantMembership.objects.create(tenant=self.tenant, user=active_user, role=TenantMembership.Role.STAFF, is_active=True)
        TenantMembership.objects.create(tenant=self.tenant, user=inactive_user, role=TenantMembership.Role.MANAGER, is_active=False)
        self.client.force_authenticate(user=admin)

        search_response = self.client.get(
            "/api/v1/tenants/current/memberships/",
            {"search": "alice"},
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(search_response.status_code, 200)
        self.assertEqual(len(search_response.data), 1)
        self.assertEqual(search_response.data[0]["email"], "alice@example.com")

        inactive_response = self.client.get(
            "/api/v1/tenants/current/memberships/",
            {"status": "inactive"},
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(inactive_response.status_code, 200)
        self.assertEqual(len(inactive_response.data), 1)
        self.assertEqual(inactive_response.data[0]["email"], "bob@example.com")
        self.assertEqual(inactive_response.data[0]["status"], "inactive")

    def test_membership_list_supports_optional_pagination(self):
        admin = User.objects.create_user(email="pageadmin@example.com", username="pageadmin", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)

        for index in range(3):
            member = User.objects.create_user(
                email=f"member{index}@example.com",
                username=f"member{index}",
                password="pass123456",
            )
            TenantMembership.objects.create(
                tenant=self.tenant,
                user=member,
                role=TenantMembership.Role.STAFF,
            )

        self.client.force_authenticate(user=admin)
        response = self.client.get(
            "/api/v1/tenants/current/memberships/",
            {"page": 2, "page_size": 2},
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 4)
        self.assertEqual(len(response.data["results"]), 2)

    def test_tenant_admin_can_update_membership_and_user_fields(self):
        admin = User.objects.create_user(email="editadmin@example.com", username="editadmin", password="pass123456")
        member = User.objects.create_user(email="editme@example.com", username="editme", password="pass123456", first_name="Before")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        membership = TenantMembership.objects.create(tenant=self.tenant, user=member, role=TenantMembership.Role.STAFF, is_active=True)
        self.client.force_authenticate(user=admin)

        response = self.client.patch(
            f"/api/v1/tenants/current/memberships/{membership.id}/",
            {
                "first_name": "After",
                "last_name": "Updated",
                "username": "updatedmember",
                "role": TenantMembership.Role.MANAGER,
                "is_active": False,
                "user_is_active": False,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 200)
        membership.refresh_from_db()
        member.refresh_from_db()
        self.assertEqual(membership.role, TenantMembership.Role.MANAGER)
        self.assertFalse(membership.is_active)
        self.assertEqual(member.first_name, "After")
        self.assertEqual(member.last_name, "Updated")
        self.assertEqual(member.username, "updatedmember")
        self.assertFalse(member.is_active)
        self.assertFalse(member.is_staff)
        self.assertEqual(response.data["status"], "inactive")

    def test_tenant_admin_can_retrieve_membership_detail(self):
        admin = User.objects.create_user(email="detailadmin@example.com", username="detailadmin", password="pass123456")
        member = User.objects.create_user(email="detail@example.com", username="detailuser", password="pass123456", first_name="Detail")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        membership = TenantMembership.objects.create(tenant=self.tenant, user=member, role=TenantMembership.Role.STAFF, is_active=True)
        self.client.force_authenticate(user=admin)

        response = self.client.get(
            f"/api/v1/tenants/current/memberships/{membership.id}/",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["id"], membership.id)
        self.assertEqual(response.data["email"], "detail@example.com")
        self.assertEqual(response.data["first_name"], "Detail")

    def test_tenant_admin_can_delete_membership_without_deleting_user(self):
        admin = User.objects.create_user(email="deleteadmin@example.com", username="deleteadmin", password="pass123456")
        member = User.objects.create_user(email="deleteme@example.com", username="deleteme", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        membership = TenantMembership.objects.create(tenant=self.tenant, user=member, role=TenantMembership.Role.STAFF, is_active=True)
        self.client.force_authenticate(user=admin)

        response = self.client.delete(
            f"/api/v1/tenants/current/memberships/{membership.id}/",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 204)
        self.assertFalse(TenantMembership.objects.filter(pk=membership.id).exists())
        member.refresh_from_db()
        self.assertTrue(User.objects.filter(pk=member.pk).exists())
        self.assertFalse(member.is_staff)

    def test_membership_endpoints_require_authentication(self):
        response = self.client.get(
            "/api/v1/tenants/current/memberships/",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 401)
