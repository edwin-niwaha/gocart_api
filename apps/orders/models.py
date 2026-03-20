from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.addresses.models import CustomerAddress
from apps.common.models import TimeStampedModel
from apps.products.models import Product, ProductVariant


class Order(TimeStampedModel):
    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        PAID = "PAID", "Paid"
        SHIPPED = "SHIPPED", "Shipped"
        DELIVERED = "DELIVERED", "Delivered"
        CANCELLED = "CANCELLED", "Cancelled"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="orders",
    )
    address = models.ForeignKey(
        CustomerAddress,
        on_delete=models.PROTECT,
        related_name="orders",
    )
    slug = models.SlugField(max_length=255, unique=True, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    description = models.TextField(blank=True)
    total_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Order"
        verbose_name_plural = "Orders"
        indexes = [
            models.Index(fields=["slug"]),
            models.Index(fields=["status"]),
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
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name="order_items",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.PROTECT,
        related_name="order_items",
    )

    product_title = models.CharField(max_length=255, editable=False)
    variant_name = models.CharField(max_length=100, editable=False)
    variant_sku = models.CharField(max_length=100, editable=False)

    quantity = models.PositiveIntegerField(
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Order Item"
        verbose_name_plural = "Order Items"
        constraints = [
            models.UniqueConstraint(
                fields=["order", "variant"],
                name="unique_variant_per_order",
            )
        ]
        indexes = [
            models.Index(fields=["order"]),
            models.Index(fields=["product"]),
            models.Index(fields=["variant"]),
            models.Index(fields=["variant_sku"]),
            models.Index(fields=["order", "variant"]),
        ]

    def __str__(self) -> str:
        return f"{self.order.slug} - {self.product_title} ({self.variant_name})"

    @property
    def line_total(self) -> Decimal:
        unit_price = self.unit_price or Decimal("0.00")
        quantity = self.quantity or 0
        return unit_price * quantity

    def clean(self) -> None:
        if self.variant_id and self.product_id and self.variant.product_id != self.product_id:
            raise ValidationError(
                {"variant": "Selected variant does not belong to the selected product."}
            )

    def save(self, *args, **kwargs):
        if self.variant_id:
            variant = self.variant
            self.product = variant.product
            self.product_title = variant.product.title
            self.variant_name = variant.name
            self.variant_sku = variant.sku

            if self.unit_price is None:
                self.unit_price = variant.price

        self.full_clean()
        super().save(*args, **kwargs)