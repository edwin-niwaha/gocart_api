from django.contrib.auth import get_user_model
from django.conf import settings
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.common.models import AuditLog, NewsletterSubscriber, SupportMessage
from apps.common.tasks import (
    send_contact_email_task,
    send_newsletter_confirmation_request_task,
    send_newsletter_subscription_confirmed_task,
)
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True, ENABLE_EMAIL=False)
class SupportMessageTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="GoCart", slug="GoCart", is_active=True, is_default=True)

    def test_contact_submission_creates_support_message(self):
        response = self.client.post(
            "/api/v1/contact/",
            {"name": "Edwin", "email": "edwin@example.com", "subject": "Help", "message": "Need help"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 201)
        support = SupportMessage.objects.get()
        self.assertEqual(support.tenant, self.tenant)
        self.assertEqual(support.status, SupportMessage.Status.NEW)
        self.assertEqual(AuditLog.objects.filter(action="support_message.created").count(), 1)

    def test_tenant_staff_can_resolve_support_message(self):
        admin = User.objects.create_user(email="admin@example.com", username="admin", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant, user=admin, role=TenantMembership.Role.STAFF)
        support = SupportMessage.objects.create(tenant=self.tenant, name="Edwin", email="edwin@example.com", message="Hello")
        self.client.force_authenticate(user=admin)
        response = self.client.patch(
            f"/api/v1/support-messages/{support.id}/",
            {"status": SupportMessage.Status.RESOLVED},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        support.refresh_from_db()
        self.assertEqual(support.status, SupportMessage.Status.RESOLVED)
        self.assertIsNotNone(support.resolved_at)


class CeleryConfigurationTests(TestCase):
    def test_worker_reliability_settings_are_enabled(self):
        self.assertTrue(settings.CELERY_TASK_ACKS_LATE)
        self.assertTrue(settings.CELERY_TASK_REJECT_ON_WORKER_LOST)
        self.assertEqual(settings.CELERY_WORKER_PREFETCH_MULTIPLIER, 1)
        self.assertTrue(settings.CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP)


class CommonTaskReliabilityTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name="Task Tenant", slug="task-tenant", is_active=True, is_default=True)

    def test_common_email_tasks_have_retry_policy(self):
        for task, max_retries in (
            (send_contact_email_task, 3),
            (send_newsletter_confirmation_request_task, 3),
            (send_newsletter_subscription_confirmed_task, 3),
        ):
            self.assertEqual(task.autoretry_for, (Exception,))
            self.assertTrue(task.retry_backoff)
            self.assertTrue(task.retry_jitter)
            self.assertEqual(task.retry_backoff_max, 300)
            self.assertEqual(task.max_retries, max_retries)

    @override_settings(ENABLE_EMAIL=False, DEFAULT_FROM_EMAIL="")
    def test_contact_email_task_skips_when_email_disabled(self):
        result = send_contact_email_task.apply(
            args=("Edwin", "edwin@example.com", "Need help"),
        ).get()

        self.assertEqual(result, {"success": False, "reason": "email disabled"})

    @override_settings(ENABLE_EMAIL=False, DEFAULT_FROM_EMAIL="")
    def test_newsletter_tasks_skip_when_email_disabled(self):
        subscriber = NewsletterSubscriber.objects.create(
            email="subscriber@example.com",
            tenant=self.tenant,
        )

        confirmation_result = send_newsletter_confirmation_request_task.apply(args=(subscriber.id,)).get()
        confirmed_result = send_newsletter_subscription_confirmed_task.apply(args=(subscriber.id,)).get()

        self.assertEqual(confirmation_result, {"success": False, "reason": "email disabled"})
        self.assertEqual(confirmed_result, {"success": False, "reason": "email disabled"})

    @override_settings(ENABLE_EMAIL=True, DEFAULT_FROM_EMAIL="noreply@example.com")
    def test_newsletter_confirmation_skips_missing_subscriber_without_retry(self):
        result = send_newsletter_confirmation_request_task.apply(args=(999999,)).get()

        self.assertEqual(result, {"success": False, "reason": "subscriber missing"})

from django.contrib.auth import get_user_model
from rest_framework.test import APITestCase
from apps.tenants.models import Tenant, TenantMembership
from apps.products.models import Category, Product, ProductVariant


class EndToEndSmokeTests(APITestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(name='Smoke Tenant', slug='smoke-tenant')
        self.user = get_user_model().objects.create_user(
            username='smokeadmin',
            email='smoke@example.com',
            password='StrongPass123!'
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.user,
            role=TenantMembership.Role.TENANT_ADMIN,
        )
        self.category = Category.objects.create(name='Groceries', tenant=self.tenant)
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            title='Coffee',
            slug='coffee',
            description='Roasted coffee'
        )
        ProductVariant.objects.create(
            tenant=self.tenant,
            product=self.product,
            name='Default',
            sku='coffee-default',
            price='15000.00',
            stock_quantity=20,
        )

    def auth_headers(self):
        login = self.client.post('/api/v1/auth/login/', {
            'email': 'smoke@example.com',
            'password': 'StrongPass123!'
        }, format='json', HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(login.status_code, 200, login.data)
        token = login.data['tokens']['access']
        return {
            'HTTP_AUTHORIZATION': f'Bearer {token}',
            'HTTP_X_TENANT_SLUG': self.tenant.slug,
        }

    def test_smoke_login_me_products_and_support(self):
        headers = self.auth_headers()
        me = self.client.get('/api/v1/auth/me/', **headers)
        self.assertEqual(me.status_code, 200)
        products = self.client.get('/api/v1/products/', **headers)
        self.assertEqual(products.status_code, 200)
        support = self.client.post('/api/v1/support-messages/', {
            'name': 'Smoke Admin',
            'email': 'smoke@example.com',
            'subject': 'Need help',
            'message': 'The smoke test needs support.'
        }, format='json', **headers)
        self.assertIn(support.status_code, (200, 201), getattr(support, 'data', None))
