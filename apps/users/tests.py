from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.products.models import Category, Product, ProductVariant
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


class GuestSessionClaimTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(
            name="Guest Claim Tenant",
            slug="guest-claim-tenant",
            is_active=True,
            is_default=True,
        )
        self.user = User.objects.create_user(
            email="guest-claim@example.com",
            username="guestclaim",
            password="pass123456",
        )
        self.category = Category.objects.create(
            tenant=self.tenant,
            name="Groceries",
            slug="groceries",
        )
        self.product = Product.objects.create(
            tenant=self.tenant,
            category=self.category,
            title="Bread",
            slug="bread",
        )
        self.checkout_variant = ProductVariant.objects.create(
            tenant=self.tenant,
            product=self.product,
            name="Loaf",
            sku="bread-loaf",
            price="4000.00",
            stock_quantity=20,
        )
        self.merge_variant = ProductVariant.objects.create(
            tenant=self.tenant,
            product=self.product,
            name="Bundle",
            sku="bread-bundle",
            price="6000.00",
            stock_quantity=20,
        )

    def test_login_claims_guest_orders_payments_and_cart_items(self):
        add_checkout_item = self.client.post(
            "/api/v1/cart-items/",
            {"variant_id": self.checkout_variant.id, "quantity": 1},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(add_checkout_item.status_code, 201)

        checkout_response = self.client.post(
            "/api/v1/orders/checkout/",
            {
                "customer_name": "Guest Shopper",
                "customer_email": self.user.email,
                "customer_phone": "0772000111",
                "street_name": "Plot 12",
                "city": "Kampala",
                "region": "kampala_area",
                "description": "guest order",
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(checkout_response.status_code, 201)

        order = Order.objects.get(slug=checkout_response.data["order"]["slug"])
        payment = Payment.objects.get(order=order)
        self.assertIsNone(order.user)
        self.assertIsNone(payment.user)
        self.assertTrue(order.guest_session_key)
        self.assertTrue(payment.guest_session_key)

        add_guest_cart_item = self.client.post(
            "/api/v1/cart-items/",
            {"variant_id": self.merge_variant.id, "quantity": 2},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(add_guest_cart_item.status_code, 201)

        user_cart = Cart.objects.create(user=self.user)
        CartItem.objects.create(
            cart=user_cart,
            variant=self.merge_variant,
            quantity=1,
            unit_price="6000.00",
        )

        login_response = self.client.post(
            "/api/v1/auth/login/",
            {"email": self.user.email, "password": "pass123456"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(login_response.status_code, 200)

        order.refresh_from_db()
        payment.refresh_from_db()
        merged_item = CartItem.objects.get(cart__user=self.user, variant=self.merge_variant)

        self.assertEqual(order.user, self.user)
        self.assertIsNone(order.guest_session_key)
        self.assertEqual(payment.user, self.user)
        self.assertIsNone(payment.guest_session_key)
        self.assertEqual(merged_item.quantity, 3)
        self.assertFalse(Cart.objects.filter(user__isnull=True).exists())
