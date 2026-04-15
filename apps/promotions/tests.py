from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone
from rest_framework.test import APIClient

from apps.promotions.models import Coupon
from apps.promotions.services import get_valid_coupon
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class CouponTenantTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        now = timezone.now()
        self.coupon_a = Coupon.objects.create(
            tenant=self.tenant_a,
            code="SAVE10",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("10"),
            starts_at=now,
            ends_at=now + timezone.timedelta(days=1),
        )
        Coupon.objects.create(
            tenant=self.tenant_b,
            code="SAVE10",
            discount_type=Coupon.DiscountType.FIXED,
            value=Decimal("5"),
            starts_at=now,
            ends_at=now + timezone.timedelta(days=1),
        )

    def test_get_valid_coupon_is_tenant_scoped(self):
        coupon = get_valid_coupon(code="save10", tenant=self.tenant_a)
        self.assertEqual(coupon.pk, self.coupon_a.pk)

    def test_tenant_manager_can_create_coupon(self):
        manager = User.objects.create_user(email="promo@example.com", username="promo", password="pass123456")
        TenantMembership.objects.create(tenant=self.tenant_a, user=manager, role=TenantMembership.Role.MANAGER)
        self.client.force_authenticate(user=manager)
        now = timezone.now()
        response = self.client.post(
            "/api/v1/coupons/",
            {
                "code": "HELLO",
                "description": "Hello",
                "discount_type": Coupon.DiscountType.FIXED,
                "value": "3.00",
                "min_order_amount": "0.00",
                "usage_limit": 0,
                "starts_at": now.isoformat(),
                "ends_at": (now + timezone.timedelta(days=1)).isoformat(),
                "is_active": True,
                "products": [],
                "categories": [],
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )
        self.assertEqual(response.status_code, 201)
        self.assertEqual(Coupon.objects.get(code="HELLO").tenant, self.tenant_a)
