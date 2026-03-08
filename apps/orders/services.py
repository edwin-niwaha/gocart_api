from django.db import transaction
from django.utils.text import slugify

from apps.inventory.services import fulfill_order_stock, release_order_stock, reserve_order_stock
from .models import Order, OrderItem


def generate_order_slug(*, user, prefix: str = "order") -> str:
    base = slugify(f"{prefix}-{user.id}")
    last_order = Order.objects.filter(user=user).count() + 1
    return f"{base}-{last_order}"


@transaction.atomic
def create_order(*, user, **validated_data) -> Order:
    if not validated_data.get("slug"):
        validated_data["slug"] = generate_order_slug(user=user)

    order = Order.objects.create(user=user, **validated_data)
    return order


@transaction.atomic
def add_order_item(*, order, product, quantity: int) -> OrderItem:
    item = OrderItem.objects.create(
        order=order,
        product=product,
        quantity=quantity,
        unit_price=product.price,
    )
    order.recalculate_total_price()
    return item


@transaction.atomic
def update_order_item(*, item: OrderItem, **validated_data) -> OrderItem:
    for attr, value in validated_data.items():
        setattr(item, attr, value)

    if "product" in validated_data and "unit_price" not in validated_data:
        item.unit_price = item.product.price

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