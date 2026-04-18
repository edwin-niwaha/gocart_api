from decimal import Decimal
from uuid import uuid4

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.utils import timezone

from apps.common.models import TimeStampedModel
from apps.orders.models import Order
from apps.tenants.models import Tenant


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

    tenant = models.ForeignKey(
        Tenant,
        on_delete=models.CASCADE,
        related_name="payments",
        null=True,
        blank=True,
    )
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
    reference = models.CharField(
        max_length=100,
        unique=True,
        db_index=True,
        editable=False,
    )
    transaction_id = models.CharField(max_length=150, blank=True)
    checkout_url = models.URLField(blank=True)
    provider_response = models.JSONField(default=dict, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["tenant", "reference"]),
            models.Index(fields=["tenant", "status"]),
            models.Index(fields=["created_at"]),
        ]

    def _sync_order_when_paid(self) -> None:
        if not self.order_id:
            return

        order = Order.objects.filter(pk=self.order_id).first()
        if not order:
            return

        if order.status in {
            Order.Status.PAID,
            Order.Status.SHIPPED,
            Order.Status.DELIVERED,
            Order.Status.REFUNDED,
            Order.Status.CANCELLED,
        }:
            return

        previous_status = order.status
        order.status = Order.Status.PAID
        order.save(update_fields=["status", "updated_at"])

        from apps.orders.models import OrderStatusEvent

        OrderStatusEvent.objects.create(
            tenant=order.tenant,
            order=order,
            changed_by=None,
            from_status=previous_status,
            to_status=Order.Status.PAID,
            note=f"Payment {self.reference} marked as PAID",
        )

    def save(self, *args, **kwargs):
        previous_status = None
        if self.pk:
            previous_status = (
                Payment.objects.filter(pk=self.pk)
                .values_list("status", flat=True)
                .first()
            )

        if not self.reference:
            self.reference = f"PAY-{uuid4().hex[:16].upper()}"

        if self.order_id and not self.tenant_id: # type: ignore
            self.tenant = self.order.tenant

        became_paid = self.status == self.Status.PAID and previous_status != self.Status.PAID
        if became_paid and not self.paid_at:
            self.paid_at = timezone.now()

        with transaction.atomic():
            super().save(*args, **kwargs)

            if became_paid:
                self._sync_order_when_paid()

    def __str__(self):
        return f"{self.reference} - {self.status}"