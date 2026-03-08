from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.services import create_notification
from apps.orders.models import Order
from .models import Shipment, ShippingMethod


@transaction.atomic
def create_shipment(*, order, address, shipping_method: ShippingMethod) -> Shipment:
    if hasattr(order, "shipment"):
        raise ValidationError("A shipment already exists for this order.")

    if order.user != address.user:
        raise ValidationError("Shipping address does not belong to the order owner.")

    shipment = Shipment.objects.create(
        order=order,
        address=address,
        shipping_method=shipping_method,
        shipping_fee=shipping_method.fee,
        status=Shipment.Status.PENDING,
    )

    create_notification(
        user=order.user,
        notification_type="SHIPPING",
        title="Shipment created",
        message=f"Shipment created for order {order.slug}.",
        data={
            "shipment_id": shipment.id, # type: ignore
            "order_slug": order.slug,
            "shipping_method": shipping_method.name,
        },
    )

    return shipment


@transaction.atomic
def mark_shipment_shipped(*, shipment: Shipment, tracking_number: str = "") -> Shipment:
    shipment.status = Shipment.Status.SHIPPED
    if tracking_number:
        shipment.tracking_number = tracking_number
    shipment.dispatched_at = timezone.now()
    shipment.save(
        update_fields=[
            "status",
            "tracking_number",
            "dispatched_at",
            "updated_at",
        ]
    )

    order = shipment.order
    if order.status in [Order.Status.PAID, Order.Status.PROCESSING]:
        order.status = Order.Status.SHIPPED
        order.save(update_fields=["status", "updated_at"])

    create_notification(
        user=shipment.order.user,
        notification_type="SHIPPING",
        title="Order shipped",
        message=f"Your order {shipment.order.slug} has been shipped.",
        data={
            "shipment_id": shipment.id, # type: ignore
            "order_slug": shipment.order.slug,
            "tracking_number": shipment.tracking_number,
        },
    )

    return shipment


@transaction.atomic
def mark_shipment_delivered(*, shipment: Shipment) -> Shipment:
    shipment.status = Shipment.Status.DELIVERED
    shipment.delivered_at = timezone.now()
    shipment.save(update_fields=["status", "delivered_at", "updated_at"])

    order = shipment.order
    order.status = Order.Status.DELIVERED
    order.save(update_fields=["status", "updated_at"])

    create_notification(
        user=shipment.order.user,
        notification_type="SHIPPING",
        title="Order delivered",
        message=f"Your order {shipment.order.slug} has been delivered.",
        data={
            "shipment_id": shipment.id, # type: ignore
            "order_slug": shipment.order.slug,
        },
    )

    return shipment


@transaction.atomic
def mark_shipment_in_transit(*, shipment: Shipment) -> Shipment:
    shipment.status = Shipment.Status.IN_TRANSIT
    shipment.save(update_fields=["status", "updated_at"])

    create_notification(
        user=shipment.order.user,
        notification_type="SHIPPING",
        title="Order in transit",
        message=f"Your order {shipment.order.slug} is in transit.",
        data={
            "shipment_id": shipment.id, # type: ignore
            "order_slug": shipment.order.slug,
            "tracking_number": shipment.tracking_number,
        },
    )

    return shipment