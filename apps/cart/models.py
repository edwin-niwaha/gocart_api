from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel
from apps.products.models import ProductVariant


class Cart(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="cart",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Cart"
        verbose_name_plural = "Carts"

    def __str__(self) -> str:
        return f"Cart ({self.user.email})"

    @property
    def total_items(self) -> int:
        return sum(item.quantity for item in self.items.all())  # type: ignore

    @property
    def total_price(self) -> Decimal:
        return sum(
            (item.line_total for item in self.items.all()),  # type: ignore
            Decimal("0.00"),
        )


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    variant = models.ForeignKey(
        ProductVariant,
        on_delete=models.CASCADE,
        related_name="cart_items",
        db_index=True,
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )
    unit_price = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "variant"],
                name="unique_variant_per_cart",
            )
        ]
        indexes = [
            models.Index(fields=["cart"]),
            models.Index(fields=["variant"]),
            models.Index(fields=["cart", "variant"]),
        ]

    def __str__(self) -> str:
        return f"{self.variant.product.title} - {self.variant.name} x {self.quantity}"

    @property
    def product(self):
        return self.variant.product

    @property
    def line_total(self) -> Decimal:
        return self.unit_price * self.quantity

    @property
    def is_available(self) -> bool:
        return (
            self.variant.is_active
            and self.variant.product.is_active
            and self.variant.stock_quantity >= self.quantity
        )

    def clean(self):
        if not self.variant.is_active:
            raise ValidationError({"variant": "This product variant is not active."})

        if not self.variant.product.is_active:
            raise ValidationError({"variant": "This product is not active."})

        if self.quantity > self.variant.stock_quantity:
            raise ValidationError(
                {"quantity": f"Only {self.variant.stock_quantity} items available in stock."}
            )

        if (
            self.variant.max_quantity_per_order is not None
            and self.quantity > self.variant.max_quantity_per_order
        ):
            raise ValidationError(
                {
                    "quantity": (
                        f"Maximum allowed quantity is "
                        f"{self.variant.max_quantity_per_order} for this item."
                    )
                }
            )

    def save(self, *args, **kwargs):
        if not self.unit_price:
            self.unit_price = self.variant.price
        self.full_clean()
        super().save(*args, **kwargs)