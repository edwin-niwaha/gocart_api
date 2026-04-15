from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.notifications.models import DeviceToken
from apps.tenants.models import Tenant

User = get_user_model()


@override_settings(ENABLE_FIREBASE=False)
class DeviceTokenApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="test@example.com", username="tester", password="secret123")
        self.tenant = Tenant.objects.create(name="GoCart", slug="gocart", is_active=True, is_default=True)
        self.client.force_authenticate(user=self.user)

    def test_register_device_token(self):
        response = self.client.post(
            "/api/v1/device-tokens/",
            {
                "token": "sample-device-token",
                "platform": "android",
                "device_id": "device-1",
                "app_version": "1.0.0",
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(DeviceToken.objects.filter(token="sample-device-token", user=self.user, tenant=self.tenant, is_active=True).exists())

    def test_unregister_device_token(self):
        DeviceToken.objects.create(user=self.user, tenant=self.tenant, token="sample-device-token", platform="android")
        response = self.client.post(
            "/api/v1/device-tokens/unregister/",
            {"token": "sample-device-token"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(DeviceToken.objects.get(token="sample-device-token").is_active)


class HealthChecksTests(TestCase):
    def test_live_endpoint(self):
        response = self.client.get("/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ok")

from apps.notifications.models import Notification
from apps.tenants.models import TenantMembership


class NotificationBroadcastTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.manager = User.objects.create_user(email="manager4@example.com", username="manager4", password="pass123456")
        self.staff = User.objects.create_user(email="staff4@example.com", username="staff4", password="pass123456")
        self.tenant = Tenant.objects.create(name="Notify", slug="notify", is_active=True, is_default=True)
        TenantMembership.objects.create(tenant=self.tenant, user=self.manager, role=TenantMembership.Role.MANAGER)
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)

    def test_manager_can_broadcast_notification(self):
        self.client.force_authenticate(user=self.manager)
        response = self.client.post(
            "/api/v1/notifications/broadcast/",
            {"title": "Update", "message": "Hello team"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Notification.objects.filter(tenant=self.tenant).count(), 2)
