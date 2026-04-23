from django.contrib.auth import get_user_model
from django.test import TestCase
from rest_framework.test import APIClient

from apps.products.models import Category, Product, ProductVariant
from apps.reviews.models import ProductRating, Review
from apps.tenants.models import Tenant

User = get_user_model()


class ReviewTenantPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="reviewer@example.com", username="reviewer", password="pass123456")
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        self.category_a = Category.objects.create(tenant=self.tenant_a, name="Fruit", slug="fruit")
        self.category_b = Category.objects.create(tenant=self.tenant_b, name="Veg", slug="veg")
        self.product_a = Product.objects.create(tenant=self.tenant_a, category=self.category_a, title="Apple", slug="apple")
        self.product_b = Product.objects.create(tenant=self.tenant_b, category=self.category_b, title="Carrot", slug="carrot")
        ProductVariant.objects.create(
            tenant=self.tenant_a,
            product=self.product_a,
            name="1kg",
            sku="apple-1kg",
            price="1000.00",
            stock_quantity=10,
        )
        ProductVariant.objects.create(
            tenant=self.tenant_b,
            product=self.product_b,
            name="1kg",
            sku="carrot-1kg",
            price="2000.00",
            stock_quantity=10,
        )

    def test_user_cannot_review_product_from_another_tenant(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            "/api/v1/reviews/",
            {"product": self.product_b.id, "rating": 5, "comment": "Wrong tenant"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Validation error.")
        self.assertIn("product", response.data["errors"])
        self.assertEqual(response.data["code"], "validation_error")
        self.assertFalse(Review.objects.exists())

    def test_public_product_reviews_are_tenant_scoped(self):
        other_user = User.objects.create_user(email="other-reviewer@example.com", username="otherreviewer", password="pass123456")
        Review.objects.create(user=self.user, product=self.product_a, rating=5, comment="Tenant A")
        Review.objects.create(user=other_user, product=self.product_b, rating=4, comment="Tenant B")

        response = self.client.get("/api/v1/product-reviews/", HTTP_X_TENANT_SLUG=self.tenant_a.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["product"], self.product_a.id)

    def test_public_product_ratings_are_tenant_scoped(self):
        ProductRating.objects.create(product=self.product_a, average_rating="5.00", total_reviews=1)
        ProductRating.objects.create(product=self.product_b, average_rating="4.00", total_reviews=1)

        response = self.client.get("/api/v1/ratings/", HTTP_X_TENANT_SLUG=self.tenant_a.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["product"], self.product_a.id)
