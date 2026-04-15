from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.addresses.models import CustomerAddress
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
from apps.products.models import Category, Product, ProductVariant
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True, ENABLE_EMAIL=False)
class OrderTenantCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="buyer@example.com", username="buyer", password="secret123")
        self.client.force_authenticate(user=self.user)
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        self.category_a = Category.objects.create(tenant=self.tenant_a, name="Fruits", slug="fruits")
        self.category_b = Category.objects.create(tenant=self.tenant_b, name="Veg", slug="veg")
        self.product_a = Product.objects.create(tenant=self.tenant_a, category=self.category_a, title="Apple", slug="apple")
        self.product_b = Product.objects.create(tenant=self.tenant_b, category=self.category_b, title="Carrot", slug="carrot")
        self.variant_a = ProductVariant.objects.create(tenant=self.tenant_a, product=self.product_a, name="1kg", sku="A1", price="1000.00", stock_quantity=10)
        self.variant_b = ProductVariant.objects.create(tenant=self.tenant_b, product=self.product_b, name="1kg", sku="B1", price="2000.00", stock_quantity=10)
        self.address = CustomerAddress.objects.create(user=self.user, street_name="Plot 1", city="Kampala", region=CustomerAddress.Region.KAMPALA_AREA)
        self.cart = Cart.objects.create(user=self.user)

    def test_checkout_uses_active_tenant_items_only(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")
        CartItem.objects.create(cart=self.cart, variant=self.variant_b, quantity=1, unit_price="2000.00")

        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": self.address.id, "description": "checkout"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(slug=response.data["slug"])
        self.assertEqual(order.tenant, self.tenant_a)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().variant, self.variant_a)


class OrderStaffVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(email="buyer2@example.com", username="buyer2", password="secret123")
        self.staff = User.objects.create_user(email="staff@example.com", username="staff", password="secret123")
        self.tenant = Tenant.objects.create(name="Tenant Staff", slug="tenant-staff", is_active=True, is_default=True)
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)
        address = CustomerAddress.objects.create(user=self.customer, street_name="Plot 2", city="Kampala", region=CustomerAddress.Region.KAMPALA_AREA)
        self.order = Order.objects.create(user=self.customer, tenant=self.tenant, address=address, status=Order.Status.PENDING, slug="ord-staff")

    def test_staff_can_list_tenant_orders(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get("/api/v1/orders/", HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)


class OrderStatusTransitionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(email="buyer3@example.com", username="buyer3", password="secret123")
        self.staff = User.objects.create_user(email="staff3@example.com", username="staff3", password="secret123")
        self.tenant = Tenant.objects.create(name="Tenant Ops", slug="tenant-ops", is_active=True, is_default=True)
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)
        address = CustomerAddress.objects.create(user=self.customer, street_name="Plot 3", city="Kampala", region=CustomerAddress.Region.KAMPALA_AREA)
        self.order = Order.objects.create(user=self.customer, tenant=self.tenant, address=address, status=Order.Status.PENDING, slug="ord-transition")

    def test_staff_can_transition_order_status(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            f"/api/v1/orders/{self.order.slug}/transition-status/",
            {"status": Order.Status.PROCESSING, "note": "Picked"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.order.status_events.count(), 1)

    def test_customer_cannot_transition_order_status(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            f"/api/v1/orders/{self.order.slug}/transition-status/",
            {"status": Order.Status.PROCESSING},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 403)
