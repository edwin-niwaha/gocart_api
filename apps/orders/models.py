from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.addresses.models import CustomerAddress
from apps.common.models import TimeStampedModel
from apps.products.models import Product, ProductVariant
from apps.tenants.models import Tenant


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        AWAITING_PAYMENT = "AWAITING_PAYMENT", "Awaiting payment"
        PROCESSING = "PROCESSING", "Processing"
        PAID = "PAID", "Paid"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"
        REFUNDED = "REFUNDED", "Refunded"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="orders", null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    address = models.ForeignKey(CustomerAddress, on_delete=models.PROTECT, related_name="orders")
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)
    description = models.TextField(blank=True)
    total_price = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"), validators=[MinValueValidator(Decimal("0.00"))])

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "slug"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self) -> str:
        return self.slug

    def recalculate_total_price(self) -> Decimal:
        total = sum((item.line_total for item in self.items.all()), Decimal("0.00"))
        self.total_price = total
        self.save(update_fields=["total_price", "updated_at"])
        return total

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())


class OrderItem(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="order_items", null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    variant = models.ForeignKey(ProductVariant, on_delete=models.PROTECT, related_name="order_items")

    product_title = models.CharField(max_length=255, editable=False)
    product_image = models.URLField(blank=True, null=True, editable=False)
    variant_name = models.CharField(max_length=100, editable=False)
    variant_sku = models.CharField(max_length=100, editable=False)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    unit_price = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])

    class Meta:
        ordering = ["created_at"]
        constraints = [models.UniqueConstraint(fields=["order", "variant"], name="unique_variant_per_order")]
        indexes = [
            models.Index(fields=["tenant", "order"]),
            models.Index(fields=["tenant", "product"]),
            models.Index(fields=["tenant", "variant"]),
            models.Index(fields=["variant_sku"]),
        ]

    def __str__(self) -> str:
        return f"{self.order.slug} - {self.product_title} ({self.variant_name})"

    @property
    def line_total(self) -> Decimal:
        return (self.unit_price or Decimal("0.00")) * (self.quantity or 0)

    def clean(self) -> None:
        if self.variant_id and self.product_id and self.variant.product_id != self.product_id:
            raise ValidationError({"variant": "Selected variant does not belong to the selected product."})
        if self.order_id and self.tenant_id and self.order.tenant_id != self.tenant_id:
            raise ValidationError({"tenant": "Order item tenant must match order tenant."})
        if self.variant_id and self.tenant_id and self.variant.tenant_id != self.tenant_id:
            raise ValidationError({"variant": "Variant must belong to the same tenant."})

    def _get_snapshot_product_image(self) -> str | None:
        if not self.variant_id:
            return None
        product = self.variant.product
        if product.hero_image:
            return product.hero_image
        if isinstance(product.image_urls, list) and product.image_urls:
            return product.image_urls[0] or None
        return None

    def save(self, *args, **kwargs):
        if self.variant_id:
            variant = self.variant
            product = variant.product
            self.tenant = variant.tenant
            self.product = product
            self.product_title = product.title
            self.product_image = self._get_snapshot_product_image()
            self.variant_name = variant.name
            self.variant_sku = variant.sku
            if self.unit_price is None:
                self.unit_price = variant.price
        self.full_clean()
        super().save(*args, **kwargs)


class OrderStatusEvent(TimeStampedModel):
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="order_status_events", null=True, blank=True)
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="status_events")
    changed_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, related_name="order_status_events", null=True, blank=True)
    from_status = models.CharField(max_length=20, choices=Order.Status.choices, blank=True)
    to_status = models.CharField(max_length=20, choices=Order.Status.choices)
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["created_at"]
        indexes = [
            models.Index(fields=["tenant", "order"]),
            models.Index(fields=["tenant", "to_status"]),
        ]

    def __str__(self) -> str:
        return f"{self.order.slug}: {self.from_status} -> {self.to_status}"
