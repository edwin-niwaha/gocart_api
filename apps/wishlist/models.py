from django.conf import settings
from django.db import models

from apps.products.models import Product
from apps.common.models import TimeStampedModel


class Wishlist(TimeStampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="wishlist",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Wishlist"
        verbose_name_plural = "Wishlists"

    def __str__(self) -> str:
        return f"Wishlist ({self.user.email})"

    @property
    def total_items(self) -> int:
        return self.items.count() # type: ignore


class WishlistItem(TimeStampedModel):
    wishlist = models.ForeignKey(
        Wishlist,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="wishlist_items",
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Wishlist Item"
        verbose_name_plural = "Wishlist Items"
        constraints = [
            models.UniqueConstraint(
                fields=["wishlist", "product"],
                name="unique_product_per_wishlist",
            )
        ]

    def __str__(self) -> str:
        return self.product.title