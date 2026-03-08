from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel
from apps.products.models import Product


class Inventory(TimeStampedModel):
    product = models.OneToOneField(
        Product,
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    stock_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    is_in_stock = models.BooleanField(default=True)

    class Meta:
        ordering = ["product__title"]

    def __str__(self):
        return f"{self.product.title} Inventory"

    @property
    def available_quantity(self):
        return max(self.stock_quantity - self.reserved_quantity, 0)

    def sync_stock_status(self):
        self.is_in_stock = self.available_quantity > 0


class InventoryMovement(TimeStampedModel):
    class MovementType(models.TextChoices):
        IN = "IN", "Stock In"
        OUT = "OUT", "Stock Out"
        RESERVED = "RESERVED", "Reserved"
        RELEASED = "RELEASED", "Released"
        ADJUSTMENT = "ADJUSTMENT", "Adjustment"

    inventory = models.ForeignKey(
        Inventory,
        on_delete=models.CASCADE,
        related_name="movements",
    )
    movement_type = models.CharField(max_length=20, choices=MovementType.choices)
    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    note = models.CharField(max_length=255, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory.product.title} - {self.movement_type} - {self.quantity}"