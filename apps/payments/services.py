from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.services import create_notification
from apps.orders.models import Order
from .models import Payment


@transaction.atomic
def create_payment(*, user, order, provider, amount, currency="UGX") -> Payment:
    if order.user != user and not user.is_staff:
        raise ValidationError("You cannot create a payment for another user's order.")

    if amount <= 0:
        raise ValidationError("Payment amount must be greater than zero.")

    if amount > order.total_price:
        raise ValidationError("Payment amount cannot exceed the order total.")

    payment = Payment.objects.create(
        user=user,
        order=order,
        provider=provider,
        amount=amount,
        currency=currency,
        status=Payment.Status.PENDING,
    )

    create_notification(
        user=user,
        notification_type="PAYMENT",
        title="Payment initiated",
        message=f"Your payment {payment.reference} has been initiated.",
        data={
            "payment_id": payment.id, # type: ignore
            "reference": payment.reference,
            "order_slug": order.slug,
        },
    )

    return payment


@transaction.atomic
def mark_payment_paid(
    *,
    payment: Payment,
    transaction_id: str = "",
    provider_response: dict | None = None,
) -> Payment:
    if payment.status == Payment.Status.PAID:
        return payment

    payment.status = Payment.Status.PAID
    payment.paid_at = timezone.now()
    payment.transaction_id = transaction_id or payment.transaction_id
    payment.provider_response = provider_response or payment.provider_response
    payment.save(
        update_fields=[
            "status",
            "paid_at",
            "transaction_id",
            "provider_response",
            "updated_at",
        ]
    )

    order = payment.order
    if order.status == Order.Status.PENDING:
        order.status = Order.Status.PAID
        order.save(update_fields=["status", "updated_at"])

    create_notification(
        user=payment.user,
        notification_type="PAYMENT",
        title="Payment successful",
        message=f"Your payment {payment.reference} was successful.",
        data={
            "payment_id": payment.id, # type: ignore
            "reference": payment.reference,
            "order_slug": order.slug,
        },
    )

    return payment


@transaction.atomic
def mark_payment_failed(
    *,
    payment: Payment,
    provider_response: dict | None = None,
) -> Payment:
    payment.status = Payment.Status.FAILED
    payment.provider_response = provider_response or payment.provider_response
    payment.save(update_fields=["status", "provider_response", "updated_at"])

    create_notification(
        user=payment.user,
        notification_type="PAYMENT",
        title="Payment failed",
        message=f"Your payment {payment.reference} failed.",
        data={
            "payment_id": payment.id, # type: ignore
            "reference": payment.reference,
            "order_slug": payment.order.slug,
        },
    )

    return payment


@transaction.atomic
def mark_payment_refunded(
    *,
    payment: Payment,
    provider_response: dict | None = None,
) -> Payment:
    payment.status = Payment.Status.REFUNDED
    payment.provider_response = provider_response or payment.provider_response
    payment.save(update_fields=["status", "provider_response", "updated_at"])

    create_notification(
        user=payment.user,
        notification_type="PAYMENT",
        title="Payment refunded",
        message=f"Your payment {payment.reference} has been refunded.",
        data={
            "payment_id": payment.id, # type: ignore
            "reference": payment.reference,
            "order_slug": payment.order.slug,
        },
    )

    return payment