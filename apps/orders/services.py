from __future__ import annotations

from uuid import uuid4

from django.db import transaction
from django.utils.text import slugify
from rest_framework.exceptions import ValidationError

from apps.common.views import create_audit_log
from apps.products.models import ProductVariant
from apps.tenants.models import Tenant
from .models import Order, OrderItem, OrderStatusEvent

ALLOWED_STATUS_TRANSITIONS = {
    Order.Status.PENDING: {Order.Status.AWAITING_PAYMENT, Order.Status.PROCESSING, Order.Status.CANCELLED},
    Order.Status.AWAITING_PAYMENT: {Order.Status.PAID, Order.Status.CANCELLED},
    Order.Status.PROCESSING: {Order.Status.PAID, Order.Status.SHIPPED, Order.Status.CANCELLED},
    Order.Status.PAID: {Order.Status.PROCESSING, Order.Status.SHIPPED, Order.Status.REFUNDED},
    Order.Status.SHIPPED: {Order.Status.DELIVERED, Order.Status.REFUNDED},
    Order.Status.DELIVERED: {Order.Status.REFUNDED},
    Order.Status.CANCELLED: set(),
    Order.Status.REFUNDED: set(),
}


def generate_order_slug(*, user, prefix: str = "order") -> str:
    return f"{slugify(prefix)}-{user.id}-{uuid4().hex[:8]}"


@transaction.atomic
def create_order(*, user, tenant: Tenant, **validated_data) -> Order:
    if not validated_data.get("slug"):
        validated_data["slug"] = generate_order_slug(user=user)
    order = Order.objects.create(user=user, tenant=tenant, **validated_data)
    OrderStatusEvent.objects.create(tenant=tenant, order=order, changed_by=user, from_status="", to_status=order.status, note="Order created")
    create_audit_log(tenant=tenant, actor=user, action="order.created", summary=f"Order {order.slug} created", target=order)
    return order


@transaction.atomic
def add_order_item(*, order: Order, variant: ProductVariant, quantity: int) -> OrderItem:
    return OrderItem.objects.create(
        tenant=order.tenant,
        order=order,
        product=variant.product,
        variant=variant,
        quantity=quantity,
        unit_price=variant.price,
    )


@transaction.atomic
def update_order_item(*, item: OrderItem, **validated_data) -> OrderItem:
    variant = validated_data.get("variant")
    for attr, value in validated_data.items():
        setattr(item, attr, value)
    if variant is not None:
        item.product = variant.product
        item.tenant = variant.tenant
        if "unit_price" not in validated_data:
            item.unit_price = variant.price
    item.save()
    item.order.recalculate_total_price()
    return item


@transaction.atomic
def remove_order_item(*, item: OrderItem) -> None:
    order = item.order
    item.delete()
    order.recalculate_total_price()


@transaction.atomic
def transition_order_status(*, order: Order, new_status: str, changed_by=None, note: str = "") -> Order:
    current_status = order.status
    if new_status == current_status:
        return order
    allowed = ALLOWED_STATUS_TRANSITIONS.get(current_status, set())
    if new_status not in allowed:
        raise ValidationError({"status": f"Cannot transition order from {current_status} to {new_status}."})
    order.status = new_status
    order.save(update_fields=["status", "updated_at"])
    OrderStatusEvent.objects.create(
        tenant=order.tenant,
        order=order,
        changed_by=changed_by,
        from_status=current_status,
        to_status=new_status,
        note=note,
    )
    create_audit_log(
        tenant=order.tenant,
        actor=changed_by,
        action="order.status_changed",
        summary=f"Order {order.slug} moved to {new_status}",
        target=order,
        metadata={"from": current_status, "to": new_status, "note": note},
    )
    return order
