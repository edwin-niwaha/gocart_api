from decimal import Decimal

from django.conf import settings
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models

from apps.products.models import Product
from apps.common.models import TimeStampedModel


class Review(TimeStampedModel):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.CASCADE,
        related_name="reviews",
    )
    rating = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    comment = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Review"
        verbose_name_plural = "Reviews"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "product"],
                name="unique_review_per_user_product",
            )
        ]
        indexes = [
            models.Index(fields=["created_at"]),
            models.Index(fields=["rating"]),
        ]

    def __str__(self) -> str:
        return f"{self.user.email} - {self.product.title}"


class ProductRating(TimeStampedModel):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="product_rating",
    )
    average_rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    total_reviews = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Product Rating"
        verbose_name_plural = "Product Ratings"

    def __str__(self) -> str:
        return f"{self.product.title} rating"