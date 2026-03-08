from django.db import transaction
from rest_framework.exceptions import ValidationError

from .models import Cart, CartItem


def get_or_create_cart(*, user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


@transaction.atomic
def add_item_to_cart(*, user, product, quantity: int) -> CartItem:
    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")

    cart = get_or_create_cart(user=user)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )

    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])

    return item


@transaction.atomic
def update_cart_item(*, item: CartItem, quantity: int) -> CartItem:
    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")

    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


@transaction.atomic
def remove_cart_item(*, item: CartItem) -> None:
    item.delete()