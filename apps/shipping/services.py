import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.notifications.services import create_notification
from apps.orders.models import Order
from .models import DeliveryRate, Shipment, ShippingMethod

logger = logging.getLogger(__name__)


def _clean_location_part(value) -> str:
    return str(value or "").strip()


def resolve_checkout_delivery_rate(
    *,
    tenant,
    delivery_option: str,
    address=None,
    address_city: str = "",
    address_region: str = "",
    address_area: str = "",
) -> DeliveryRate | None:
    if tenant is None or delivery_option != Order.DeliveryOption.HOME_DELIVERY:
        return None

    region = _clean_location_part(address_region or getattr(address, "region", ""))
    city = _clean_location_part(address_city or getattr(address, "city", ""))
    area = _clean_location_part(address_area or getattr(address, "area", ""))

    if not region:
        return None

    rates = DeliveryRate.objects.filter(
        tenant=tenant,
        is_active=True,
        region=region,
    ).order_by("fee", "estimated_days", "id")

    if area and city:
        exact_rate = rates.filter(city__iexact=city, area__iexact=area).first()
        if exact_rate is not None:
            return exact_rate

    if city:
        city_rate = rates.filter(city__iexact=city, area="").first()
        if city_rate is not None:
            return city_rate

    return rates.filter(city="", area="").first()


def resolve_checkout_shipping_method(*, delivery_option: str) -> ShippingMethod | None:
    if delivery_option != Order.DeliveryOption.HOME_DELIVERY:
        return None

    queryset = ShippingMethod.objects.filter(is_active=True).order_by(
        "fee",
        "estimated_days",
        "id",
    )
    shipping_method = queryset.first()

    if shipping_method is not None and queryset[1:2].exists():
        logger.warning(
            "Multiple active shipping methods found for home delivery checkout; "
            "using shipping_method_id=%s",
            shipping_method.id,
        )

    return shipping_method


def get_checkout_shipping_fee(
    *,
    tenant=None,
    delivery_option: str,
    pickup_station=None,
    shipping_method: ShippingMethod | None = None,
    address=None,
    address_city: str = "",
    address_region: str = "",
    address_area: str = "",
) -> Decimal:
    if delivery_option == Order.DeliveryOption.PICKUP_STATION:
        return Decimal("0.00")

    delivery_rate = resolve_checkout_delivery_rate(
        tenant=tenant,
        delivery_option=delivery_option,
        address=address,
        address_city=address_city,
        address_region=address_region,
        address_area=address_area,
    )
    if delivery_rate is not None:
        return delivery_rate.fee

    raise ValidationError("Delivery is not available for this location.")


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
        shipping_fee=order.shipping_fee,
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
