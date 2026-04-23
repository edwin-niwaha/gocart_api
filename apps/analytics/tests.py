from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.addresses.models import CustomerAddress
from apps.analytics.serializers import DashboardSummaryQuerySerializer
from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.products.models import Category, Product, ProductVariant
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class AdminDashboardSummaryTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Analytics Tenant",
            slug="analytics-tenant",
            is_active=True,
            is_default=True,
        )
        self.other_tenant = Tenant.objects.create(
            name="Other Tenant",
            slug="other-analytics-tenant",
            is_active=True,
        )
        self.manager = User.objects.create_user(
            email="manager@example.com",
            username="manager",
            password="secret123",
        )
        self.customer = User.objects.create_user(
            email="buyer@example.com",
            username="buyer",
            password="secret123",
        )
        self.other_customer = User.objects.create_user(
            email="other-buyer@example.com",
            username="otherbuyer",
            password="secret123",
        )
        TenantMembership.objects.create(
            tenant=self.tenant,
            user=self.manager,
            role=TenantMembership.Role.MANAGER,
        )
        category = Category.objects.create(
            tenant=self.tenant,
            name="Fruits",
            slug="analytics-fruits",
        )
        other_category = Category.objects.create(
            tenant=self.other_tenant,
            name="Fruits",
            slug="other-analytics-fruits",
        )
        product = Product.objects.create(
            tenant=self.tenant,
            category=category,
            title="Apple",
            slug="analytics-apple",
        )
        other_product = Product.objects.create(
            tenant=self.other_tenant,
            category=other_category,
            title="Orange",
            slug="other-analytics-orange",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant,
            product=product,
            name="1kg",
            sku="AN-APPLE-1KG",
            price="1000.00",
            stock_quantity=3,
        )
        self.other_variant = ProductVariant.objects.create(
            tenant=self.other_tenant,
            product=other_product,
            name="1kg",
            sku="AN-ORANGE-1KG",
            price="2000.00",
            stock_quantity=1,
        )
        self.address = CustomerAddress.objects.create(
            user=self.customer,
            street_name="Plot 1",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        other_address = CustomerAddress.objects.create(
            user=self.other_customer,
            street_name="Plot 2",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        order = Order.objects.create(
            tenant=self.tenant,
            user=self.customer,
            address=self.address,
            slug="analytics-order",
            status=Order.Status.PAID,
            total_price="2000.00",
        )
        OrderItem.objects.create(
            tenant=self.tenant,
            order=order,
            product=product,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        Payment.objects.create(
            tenant=self.tenant,
            user=self.customer,
            order=order,
            provider=Payment.Provider.CASH,
            status=Payment.Status.PAID,
            amount="2000.00",
        )
        other_order = Order.objects.create(
            tenant=self.other_tenant,
            user=self.other_customer,
            address=other_address,
            slug="other-analytics-order",
            status=Order.Status.PAID,
            total_price="2000.00",
        )
        OrderItem.objects.create(
            tenant=self.other_tenant,
            order=other_order,
            product=other_product,
            variant=self.other_variant,
            quantity=1,
            unit_price="2000.00",
        )

    def test_manager_gets_tenant_scoped_dashboard_summary(self):
        self.client.force_authenticate(user=self.manager)

        response = self.client.get(
            "/api/v1/admin/dashboard/summary/",
            {"low_stock_threshold": 5},
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["orders"]["total"], 1)
        self.assertEqual(response.data["orders"]["by_status"][Order.Status.PAID], 1)
        self.assertEqual(response.data["revenue"]["collected"], "2000.00")
        self.assertEqual(response.data["customers"]["unique_buyers"], 1)
        self.assertEqual(response.data["inventory"]["low_stock"], 1)
        self.assertEqual(response.data["low_stock_variants"][0]["sku"], self.variant.sku)
        self.assertEqual(response.data["top_products"][0]["product_title"], "Apple")
        self.assertNotIn("Orange", str(response.data))

    def test_customer_cannot_access_dashboard_summary(self):
        self.client.force_authenticate(user=self.customer)

        response = self.client.get(
            "/api/v1/admin/dashboard/summary/",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 403)


class DashboardSummaryQuerySerializerTests(TestCase):
    def test_rejects_ranges_over_one_year(self):
        serializer = DashboardSummaryQuerySerializer(
            data={
                "date_from": "2024-01-01",
                "date_to": "2025-01-02",
            }
        )

        self.assertFalse(serializer.is_valid())
        self.assertIn("date_to", serializer.errors)
