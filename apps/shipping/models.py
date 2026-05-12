from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import models

from apps.addresses.models import CustomerAddress
from apps.common.models import TimeStampedModel
from apps.tenants.models import Tenant


class ShippingMethod(TimeStampedModel):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    estimated_days = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class PickupStation(TimeStampedModel):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="pickup_stations",
        null=True,
        blank=True,
    )
    name = models.CharField(max_length=255)
    city = models.CharField(max_length=100)
    area = models.CharField(max_length=100)
    address = models.TextField()
    phone = models.CharField(max_length=50, blank=True)
    opening_hours = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["city", "area", "name"]
        indexes = [
            models.Index(fields=["tenant", "city", "area"]),
            models.Index(fields=["tenant", "is_active"]),
        ]

    def __str__(self):
        return f"{self.name} - {self.area}"


class DeliveryRate(TimeStampedModel):
    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="delivery_rates",
    )
    region = models.CharField(
        max_length=30,
        choices=CustomerAddress.Region.choices,
        db_index=True,
    )
    city = models.CharField(max_length=100, blank=True, db_index=True)
    area = models.CharField(max_length=100, blank=True, db_index=True)
    fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    estimated_days = models.PositiveIntegerField(default=1)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["region", "city", "area", "fee", "estimated_days", "id"]
        indexes = [
            models.Index(
                fields=["tenant", "is_active"],
                name="ship_delrate_tenant_active_idx",
            ),
            models.Index(
                fields=["tenant", "region", "city", "area"],
                name="ship_delrate_tenant_loc_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["tenant", "region", "city", "area"],
                name="unique_delivery_rate_per_location",
            ),
        ]

    def __str__(self):
        location_parts = [self.get_region_display()]
        if self.city:
            location_parts.append(self.city)
        if self.area:
            location_parts.append(self.area)
        return " / ".join(location_parts)
