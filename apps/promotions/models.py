from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.products.models import Category, Product
from apps.tenants.models import Tenant


class Coupon(TimeStampedModel):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "PERCENTAGE", "Percentage"
        FIXED = "FIXED", "Fixed"

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name="coupons", null=True, blank=True)
    code = models.CharField(max_length=50, db_index=True)
    description = models.CharField(max_length=255, blank=True)
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    value = models.DecimalField(max_digits=12, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))])
    min_order_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    max_discount_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    usage_limit = models.PositiveIntegerField(default=0)
    used_count = models.PositiveIntegerField(default=0)
    starts_at = models.DateTimeField()
    ends_at = models.DateTimeField()
    is_active = models.BooleanField(default=True)
    products = models.ManyToManyField(Product, blank=True, related_name="coupons")
    categories = models.ManyToManyField(Category, blank=True, related_name="coupons")

    class Meta:
        ordering = ["-created_at"]
        constraints = [models.UniqueConstraint(fields=["tenant", "code"], name="unique_coupon_code_per_tenant")]
        indexes = [models.Index(fields=["tenant", "code"]), models.Index(fields=["tenant", "is_active"])]

    def __str__(self):
        return self.code

    def clean(self):
        if self.starts_at and self.ends_at and self.starts_at > self.ends_at:
            raise ValidationError({"ends_at": "End date must be after start date."})

    @property
    def is_valid_now(self):
        now = timezone.now()
        return (
            self.is_active
            and self.starts_at is not None
            and self.ends_at is not None
            and self.starts_at <= now <= self.ends_at
            and (self.usage_limit == 0 or self.used_count < self.usage_limit)
        )