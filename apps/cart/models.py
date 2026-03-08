from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.products.models import Product
from apps.common.models import TimeStampedModel


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
        return sum(item.quantity for item in self.items.all()) # type: ignore

    @property
    def total_price(self) -> Decimal:
        return sum(
            (item.line_total for item in self.items.all()), # type: ignore
            Decimal("0.00"),
        )


class CartItem(TimeStampedModel):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Cart Item"
        verbose_name_plural = "Cart Items"
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_product_per_cart",
            )
        ]

    def __str__(self) -> str:
        return f"{self.product.title} x {self.quantity}"

    @property
    def unit_price(self):
        return self.product.price

    @property
    def line_total(self):
        return self.product.price * self.quantity