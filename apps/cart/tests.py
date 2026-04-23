from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.products.models import Category, Product, ProductVariant
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class CartTenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="cart-user@example.com",
            username="cartuser",
            password="pass123456",
        )
        self.client.force_authenticate(user=self.user)
        self.tenant_a = Tenant.objects.create(
            name="Cart Tenant A",
            slug="cart-tenant-a",
            is_active=True,
            is_default=True,
        )
        self.tenant_b = Tenant.objects.create(
            name="Cart Tenant B",
            slug="cart-tenant-b",
            is_active=True,
        )
        self.category_a = Category.objects.create(tenant=self.tenant_a, name="Fruit", slug="fruit")
        self.category_b = Category.objects.create(tenant=self.tenant_b, name="Veg", slug="veg")
        self.product_a = Product.objects.create(
            tenant=self.tenant_a,
            category=self.category_a,
            title="Apple",
            slug="apple",
        )
        self.product_b = Product.objects.create(
            tenant=self.tenant_b,
            category=self.category_b,
            title="Carrot",
            slug="carrot",
        )
        self.variant_a = ProductVariant.objects.create(
            tenant=self.tenant_a,
            product=self.product_a,
            name="1kg",
            sku="cart-a-1kg",
            price="1000.00",
            stock_quantity=10,
        )
        self.variant_b = ProductVariant.objects.create(
            tenant=self.tenant_b,
            product=self.product_b,
            name="1kg",
            sku="cart-b-1kg",
            price="2000.00",
            stock_quantity=10,
        )
        self.cart = Cart.objects.create(user=self.user)

    def test_cart_response_filters_items_and_totals_to_active_tenant(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=1, unit_price="1000.00")
        CartItem.objects.create(cart=self.cart, variant=self.variant_b, quantity=3, unit_price="2000.00")

        response = self.client.post(
            "/api/v1/cart/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["variant"]["id"], self.variant_a.id)
        self.assertEqual(response.data["total_items"], 1)
        self.assertEqual(Decimal(str(response.data["total_price"])), Decimal("1000.00"))

    def test_tenant_staff_can_only_access_their_own_cart_items(self):
        staff = User.objects.create_user(
            email="seller-cart@example.com",
            username="sellercart",
            password="pass123456",
        )
        TenantMembership.objects.create(
            tenant=self.tenant_a,
            user=staff,
            role=TenantMembership.Role.STAFF,
        )
        staff_cart = Cart.objects.create(user=staff)
        staff_item = CartItem.objects.create(
            cart=staff_cart,
            variant=self.variant_a,
            quantity=2,
            unit_price="1000.00",
        )
        customer_item = CartItem.objects.create(
            cart=self.cart,
            variant=self.variant_a,
            quantity=1,
            unit_price="1000.00",
        )
        self.client.force_authenticate(user=staff)

        response = self.client.get(
            "/api/v1/cart-items/",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 200)
        item_ids = [item["id"] for item in response.data["results"]]
        self.assertEqual(item_ids, [staff_item.id])
        self.assertNotIn(customer_item.id, item_ids)


class GuestCartSessionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Guest Cart Tenant",
            slug="guest-cart-tenant",
            is_active=True,
            is_default=True,
        )
        self.category = Category.objects.create(
            tenant=self.tenant,
            name="Snacks",
            slug="snacks",
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            title="Biscuits",
            slug="biscuits",
        )
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant,
            product=self.product,
            name="Pack",
            sku="guest-biscuits-pack",
            price="2500.00",
            stock_quantity=12,
        )

    def test_guest_cart_uses_session_owner_and_returns_items(self):
        add_response = self.client.post(
            "/api/v1/cart-items/",
            {"variant_id": self.variant.id, "quantity": 2},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        cart_response = self.client.post(
            "/api/v1/cart/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(add_response.status_code, 201)
        self.assertEqual(cart_response.status_code, 200)
        self.assertIsNone(cart_response.data["user"])
        self.assertEqual(cart_response.data["total_items"], 2)
        self.assertEqual(Decimal(str(cart_response.data["total_price"])), Decimal("5000.00"))
        self.assertEqual(len(cart_response.data["items"]), 1)

        cart = Cart.objects.get()
        self.assertIsNone(cart.user)
        self.assertTrue(cart.guest_session_key)
