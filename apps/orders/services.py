from __future__ import annotations

from uuid import uuid4

from django.db import transaction
from django.utils.text import slugify

from apps.inventory.services import fulfill_order_stock, release_order_stock, reserve_order_stock
from apps.products.models import ProductVariant
from .models import Order, OrderItem


def generate_order_slug(*, user, prefix: str = "order") -> str:
    return f"{slugify(prefix)}-{user.id}-{uuid4().hex[:8]}"


@transaction.atomic
def create_order(*, user, **validated_data) -> Order:
    if not validated_data.get("slug"):
        validated_data["slug"] = generate_order_slug(user=user)

    return Order.objects.create(user=user, **validated_data)


@transaction.atomic
def add_order_item(*, order: Order, variant: ProductVariant, quantity: int) -> OrderItem:
    return OrderItem.objects.create(
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
def reserve_stock_for_order(*, order: Order) -> None:
    reserve_order_stock(order=order)


@transaction.atomic
def release_stock_for_order(*, order: Order) -> None:
    release_order_stock(order=order)


@transaction.atomic
def fulfill_stock_for_order(*, order: Order) -> None:
    fulfill_order_stock(order=order)