from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel
from apps.tenants.models import Tenant


class Category(TimeStampedModel):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="categories",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, db_index=True)
    image_url = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]
        verbose_name = "Category"
        verbose_name_plural = "Categories"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "name"], name="unique_category_name_per_tenant"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="unique_category_slug_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["tenant", "name"]),
            models.Index(fields=["tenant", "slug"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.tenant.slug}: {self.name}" if self.tenant else self.name


class Product(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="products", null=True, blank=True)
    category = models.ForeignKey(
        Category,
        on_delete=models.CASCADE,
        related_name="products",
        db_index=True,
    )

    title = models.CharField(max_length=255, db_index=True)
    slug = models.SlugField(max_length=255, db_index=True)

    description = models.TextField(blank=True)
    hero_image = models.URLField(blank=True, null=True)
    image_urls = models.JSONField(default=list, blank=True)

    is_active = models.BooleanField(default=True)
    is_featured = models.BooleanField(default=False)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Product"
        verbose_name_plural = "Products"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "title"], name="unique_product_title_per_tenant"),
            models.UniqueConstraint(fields=["tenant", "slug"], name="unique_product_slug_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["tenant", "title"]),
            models.Index(fields=["tenant", "slug"]),
            models.Index(fields=["tenant", "category"]),
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["tenant", "is_featured", "is_active"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self) -> str:
        return self.title

    @property
    def primary_image(self) -> str | None:
        if self.hero_image:
            return self.hero_image
        if isinstance(self.image_urls, list):
            for image_url in self.image_urls:
                if image_url:
                    return image_url
        return None

    @property
    def base_price(self):
        first_variant = self.variants.filter(is_active=True).order_by("price").first()  # type: ignore
        return first_variant.price if first_variant else Decimal("0.00")

    @property
    def is_in_stock(self) -> bool:
        return self.variants.filter(is_active=True, stock_quantity__gt=0).exists()  # type: ignore


class ProductVariant(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="product_variants", null=True, blank=True)
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="variants",
        db_index=True,
    )

    name = models.CharField(max_length=100)
    sku = models.CharField(max_length=100, db_index=True)

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
        constraints = [
            models.UniqueConstraint(fields=["product", "name"], name="unique_variant_name_per_product"),
            models.UniqueConstraint(fields=["tenant", "sku"], name="unique_variant_sku_per_tenant"),
        ]
        indexes = [
            models.Index(fields=["tenant", "product"]),
            models.Index(fields=["tenant", "sku"]),
            models.Index(fields=["tenant", "price"]),
            models.Index(fields=["tenant", "stock_quantity"]),
            models.Index(fields=["tenant", "is_active"]),
            models.Index(fields=["product", "is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.product.title} - {self.name}"

    @property
    def is_in_stock(self) -> bool:
        return self.stock_quantity > 0

    def save(self, *args, **kwargs):
        if self.product_id and not self.tenant_id:
            self.tenant = self.product.tenant
        super().save(*args, **kwargs)
