from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from apps.common.models import TimeStampedModel
from apps.orders.models import Order


class Payment(TimeStampedModel):
    class Provider(models.TextChoices):
        CASH = "CASH", "Cash"
        STRIPE = "STRIPE", "Stripe"
        PAYSTACK = "PAYSTACK", "Paystack"
        FLUTTERWAVE = "FLUTTERWAVE", "Flutterwave"
        MTN = "MTN", "MTN Mobile Money"
        AIRTEL = "AIRTEL", "Airtel Money"

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        PAID = "PAID", "Paid"
        FAILED = "FAILED", "Failed"
        REFUNDED = "REFUNDED", "Refunded"
        CANCELLED = "CANCELLED", "Cancelled"

    class Currency(models.TextChoices):
        UGX = "UGX", "Ugandan Shilling"
        EUR = "EUR", "Euro"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payments",
    )
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
    provider = models.CharField(max_length=20, choices=Provider.choices)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    currency = models.CharField(
        max_length=10,
        choices=Currency.choices,
        default=Currency.UGX,
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    phone_number = models.CharField(max_length=20, blank=True)
    external_id = models.CharField(max_length=100, blank=True)
    reference = models.CharField(max_length=100, unique=True, db_index=True, editable=False)
    transaction_id = models.CharField(max_length=150, blank=True)
    checkout_url = models.URLField(blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["reference"]),
            models.Index(fields=["status"]),
            models.Index(fields=["created_at"]),
        ]

    def save(self, *args, **kwargs):
        if not self.reference:
            self.reference = f"PAY-{uuid4().hex[:16].upper()}"
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.reference} - {self.status}"