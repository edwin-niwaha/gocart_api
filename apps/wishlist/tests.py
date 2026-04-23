from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.models import Category, Product, ProductVariant
from apps.tenants.models import Tenant
from apps.wishlist.models import Wishlist, WishlistItem

User = get_user_model()


class WishlistTenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            email="wishlist-user@example.com",
            username="wishlistuser",
            password="pass123456",
        )
        self.client.force_authenticate(user=self.user)
        self.tenant_a = Tenant.objects.create(
            name="Wishlist Tenant A",
            slug="wishlist-tenant-a",
            is_active=True,
            is_default=True,
        )
        self.tenant_b = Tenant.objects.create(
            name="Wishlist Tenant B",
            slug="wishlist-tenant-b",
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
        ProductVariant.objects.create(
            tenant=self.tenant_a,
            product=self.product_a,
            name="1kg",
            sku="wishlist-a-1kg",
            price="1000.00",
            stock_quantity=10,
        )
        ProductVariant.objects.create(
            tenant=self.tenant_b,
            product=self.product_b,
            name="1kg",
            sku="wishlist-b-1kg",
            price="2000.00",
            stock_quantity=10,
        )
        self.wishlist = Wishlist.objects.create(user=self.user)

    def test_wishlist_response_filters_items_to_active_tenant(self):
        WishlistItem.objects.create(wishlist=self.wishlist, product=self.product_a)
        WishlistItem.objects.create(wishlist=self.wishlist, product=self.product_b)

        response = self.client.post(
            "/api/v1/wishlist/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["items"]), 1)
        self.assertEqual(response.data["items"][0]["product"]["id"], self.product_a.id)
        self.assertEqual(response.data["total_items"], 1)
