from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Inventory, InventoryMovement


def get_or_create_inventory(*, product) -> Inventory:
    inventory, _ = Inventory.objects.get_or_create(product=product)
    inventory.sync_stock_status()
    inventory.save(update_fields=["is_in_stock", "updated_at"])
    return inventory


@transaction.atomic
def increase_stock(*, product, quantity: int, note: str = "") -> InventoryMovement:
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    inventory = get_or_create_inventory(product=product)
    inventory.stock_quantity += quantity
    inventory.sync_stock_status()
    inventory.save(update_fields=["stock_quantity", "is_in_stock", "updated_at"])

    return InventoryMovement.objects.create(
        inventory=inventory,
        movement_type=InventoryMovement.MovementType.IN,
        quantity=quantity,
        note=note,
    )


@transaction.atomic
def decrease_stock(*, product, quantity: int, note: str = "") -> InventoryMovement:
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    inventory = get_or_create_inventory(product=product)

    if inventory.available_quantity < quantity:
        raise ValidationError("Insufficient stock available.")

    inventory.stock_quantity -= quantity
    inventory.sync_stock_status()
    inventory.save(update_fields=["stock_quantity", "is_in_stock", "updated_at"])

    return InventoryMovement.objects.create(
        inventory=inventory,
        movement_type=InventoryMovement.MovementType.OUT,
        quantity=quantity,
        note=note,
    )


@transaction.atomic
def reserve_stock(*, product, quantity: int, note: str = "") -> InventoryMovement:
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    inventory = get_or_create_inventory(product=product)

    if inventory.available_quantity < quantity:
        raise ValidationError("Insufficient stock available to reserve.")

    inventory.reserved_quantity += quantity
    inventory.sync_stock_status()
    inventory.save(update_fields=["reserved_quantity", "is_in_stock", "updated_at"])

    return InventoryMovement.objects.create(
        inventory=inventory,
        movement_type=InventoryMovement.MovementType.RESERVED,
        quantity=quantity,
        note=note,
    )


@transaction.atomic
def release_reserved_stock(*, product, quantity: int, note: str = "") -> InventoryMovement:
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    inventory = get_or_create_inventory(product=product)

    if inventory.reserved_quantity < quantity:
        raise ValidationError("Reserved quantity is lower than the release amount.")

    inventory.reserved_quantity -= quantity
    inventory.sync_stock_status()
    inventory.save(update_fields=["reserved_quantity", "is_in_stock", "updated_at"])

    return InventoryMovement.objects.create(
        inventory=inventory,
        movement_type=InventoryMovement.MovementType.RELEASED,
        quantity=quantity,
        note=note,
    )


@transaction.atomic
def fulfill_reserved_stock(*, product, quantity: int, note: str = "") -> None:
    if quantity <= 0:
        raise ValidationError("Quantity must be greater than zero.")

    inventory = get_or_create_inventory(product=product)

    if inventory.reserved_quantity < quantity:
        raise ValidationError("Reserved quantity is lower than the fulfillment amount.")

    if inventory.stock_quantity < quantity:
        raise ValidationError("Stock quantity is lower than the fulfillment amount.")

    inventory.reserved_quantity -= quantity
    inventory.stock_quantity -= quantity
    inventory.sync_stock_status()
    inventory.save(
        update_fields=[
            "reserved_quantity",
            "stock_quantity",
            "is_in_stock",
            "updated_at",
        ]
    )

    InventoryMovement.objects.create(
        inventory=inventory,
        movement_type=InventoryMovement.MovementType.OUT,
        quantity=quantity,
        note=note or "Reserved stock fulfilled",
    )


@transaction.atomic
def reserve_order_stock(*, order) -> None:
    for item in order.items.select_related("product").all():
        reserve_stock(
            product=item.product,
            quantity=item.quantity,
            note=f"Reserved for order {order.slug}",
        )


@transaction.atomic
def fulfill_order_stock(*, order) -> None:
    for item in order.items.select_related("product").all():
        fulfill_reserved_stock(
            product=item.product,
            quantity=item.quantity,
            note=f"Fulfilled for order {order.slug}",
        )


@transaction.atomic
def release_order_stock(*, order) -> None:
    for item in order.items.select_related("product").all():
        release_reserved_stock(
            product=item.product,
            quantity=item.quantity,
            note=f"Released for order {order.slug}",
        )