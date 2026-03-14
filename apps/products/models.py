from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models
from apps.common.models import TimeStampedModel


class Category(TimeStampedModel):
    name = models.CharField(max_length=255, unique=True, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name


class Product(TimeStampedModel):
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )

    title = models.CharField(max_length=255, unique=True, db_index=True)
    slug = models.SlugField(max_length=255, unique=True, db_index=True)

    description = models.TextField(blank=True)
    hero_image = models.URLField(blank=True, null=True)
    image_urls = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"
        indexes = [
            models.Index(fields=["title"]),
            models.Index(fields=["slug"]),
            models.Index(fields=["category"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["is_featured"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["category", "is_active"]),
            models.Index(fields=["is_featured", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def base_price(self):
        first_variant = self.variants.filter(is_active=True).order_by("price").first()  # type: ignore
        return first_variant.price if first_variant else Decimal("0.00")

    @property
    def is_in_stock(self) -> bool:
        return self.variants.filter(is_active=True, stock_quantity__gt=0).exists()  # type: ignore


class ProductVariant(TimeStampedModel):
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        db_index=True,
    )

    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=100, unique=True, db_index=True)

    price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
        db_index=True,
    )

    stock_quantity = models.PositiveIntegerField(default=0)
    max_quantity_per_order = models.PositiveIntegerField(null=True, blank=True)

    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "price", "id"]
        unique_together = ("product", "name")
        indexes = [
            models.Index(fields=["product"]),
            models.Index(fields=["sku"]),
            models.Index(fields=["price"]),
            models.Index(fields=["stock_quantity"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["product", "is_active"]),
            models.Index(fields=["product", "price"]),
            models.Index(fields=["product", "stock_quantity"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.title} - {self.name}"

    @property
    def is_in_stock(self) -> bool:
        return self.stock_quantity > 0