from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.models import Category, Product, ProductVariant
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class ProductTenantIsolationTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        self.category_a = Category.objects.create(tenant=self.tenant_a, name="Fruits", slug="fruits")
        self.category_b = Category.objects.create(tenant=self.tenant_b, name="Fruits", slug="fruits")
        self.product_a = Product.objects.create(tenant=self.tenant_a, category=self.category_a, title="Apple", slug="apple")
        self.product_b = Product.objects.create(tenant=self.tenant_b, category=self.category_b, title="Apple", slug="apple")
        ProductVariant.objects.create(tenant=self.tenant_a, product=self.product_a, name="1kg", sku="A1", price="1000.00", stock_quantity=10)
        ProductVariant.objects.create(tenant=self.tenant_b, product=self.product_b, name="1kg", sku="B1", price="2000.00", stock_quantity=10)

    def test_list_products_returns_active_tenant_only(self):
        response = self.client.get("/api/v1/products/", HTTP_X_TENANT_SLUG=self.tenant_a.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data["results"]), 1)
        self.assertEqual(response.data["results"][0]["slug"], self.product_a.slug)

    def test_admin_create_product_is_scoped_to_active_tenant(self):
        admin = User.objects.create_user(email="admin@example.com", username="admin", password="secret123", is_staff=True)
        TenantMembership.objects.create(tenant=self.tenant_a, user=admin, role=TenantMembership.Role.TENANT_ADMIN)
        self.client.force_authenticate(user=admin)
        response = self.client.post(
            "/api/v1/products/",
            {
                "title": "Banana",
                "description": "Fresh",
                "category_id": self.category_a.id,
                "variants": [{"name": "Tray", "price": "3000.00", "stock_quantity": 5}],
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )
        self.assertEqual(response.status_code, 201)
        self.assertTrue(Product.objects.filter(tenant=self.tenant_a, title="Banana").exists())


class ProductRolePermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant = Tenant.objects.create(name="Tenant A", slug="tenant-a-role", is_active=True, is_default=True)
        self.category = Category.objects.create(tenant=self.tenant, name="Fruits", slug="fruits-role")

    def test_manager_cannot_create_product(self):
        manager = User.objects.create_user(email="manager2@example.com", username="manager2", password="secret123")
        TenantMembership.objects.create(tenant=self.tenant, user=manager, role=TenantMembership.Role.MANAGER)
        self.client.force_authenticate(user=manager)
        response = self.client.post("/api/v1/products/", {"title": "Pear", "description": "Fresh", "category_id": self.category.id, "variants": [{"name": "Pack", "price": "1000.00", "stock_quantity": 3}]}, format="json", HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(response.status_code, 403)
