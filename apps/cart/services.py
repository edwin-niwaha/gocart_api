from django.db import transaction
from rest_framework.exceptions import ValidationError

from apps.products.models import ProductVariant
from apps.tenants.models import Tenant
from .models import Cart, CartItem


def get_or_create_cart(*, user) -> Cart:
    cart, _ = Cart.objects.get_or_create(user=user)
    return cart


def _validate_variant_quantity(*, variant: ProductVariant, quantity: int, tenant: Tenant | None = None) -> None:
    if quantity < 1:
        raise ValidationError("Quantity must be at least 1.")

    if tenant is not None and variant.tenant_id != tenant.id:
        raise ValidationError("This variant does not belong to the active tenant.")

    if not variant.is_active:
        raise ValidationError("This product variant is not active.")

    if not variant.product.is_active:
        raise ValidationError("This product is not active.")

    if quantity > variant.stock_quantity:
        raise ValidationError(
            f"Only {variant.stock_quantity} items available in stock."
        )

    if (
        variant.max_quantity_per_order is not None
        and quantity > variant.max_quantity_per_order
    ):
        raise ValidationError(
            f"Maximum allowed quantity is {variant.max_quantity_per_order} for this item."
        )


@transaction.atomic
def add_item_to_cart(*, user, variant: ProductVariant, quantity: int, tenant: Tenant) -> CartItem:
    cart = get_or_create_cart(user=user)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        variant=variant,
        defaults={
            "quantity": quantity,
            "unit_price": variant.price,
        },
    )

    if created:
        _validate_variant_quantity(variant=variant, quantity=item.quantity, tenant=tenant)
        return item

    new_quantity = item.quantity + quantity
    _validate_variant_quantity(variant=variant, quantity=new_quantity, tenant=tenant)

    item.quantity = new_quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


@transaction.atomic
def update_cart_item(*, item: CartItem, quantity: int, tenant: Tenant) -> CartItem:
    _validate_variant_quantity(variant=item.variant, quantity=quantity, tenant=tenant)
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    return item


@transaction.atomic
def remove_cart_item(*, item: CartItem) -> None:
    item.delete()
