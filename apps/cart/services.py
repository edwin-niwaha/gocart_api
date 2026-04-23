from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.products.models import ProductVariant
from apps.tenants.models import Tenant
from .models import Cart, CartItem


def _build_cart_owner_lookup(*, user=None, guest_session_key: str | None = None) -> dict:
    authenticated_user = user if getattr(user, "is_authenticated", False) else None

    if authenticated_user is not None and guest_session_key:
        raise ValueError("Cart owner must be either a user or a guest session.")
    if authenticated_user is not None:
        return {"user": authenticated_user}
    if guest_session_key:
        return {"guest_session_key": guest_session_key}
    raise ValueError("Cart owner is required.")


def get_or_create_cart(*, user=None, guest_session_key: str | None = None) -> Cart:
    lookup = _build_cart_owner_lookup(user=user, guest_session_key=guest_session_key)
    cart, _ = Cart.objects.get_or_create(**lookup)
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
def add_item_to_cart(
    *,
    user=None,
    guest_session_key: str | None = None,
    variant: ProductVariant,
    quantity: int,
    tenant: Tenant,
) -> CartItem:
    cart = get_or_create_cart(user=user, guest_session_key=guest_session_key)

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


@transaction.atomic
def claim_guest_cart(*, user, guest_session_key: str | None) -> dict[str, int]:
    if not guest_session_key or not getattr(user, "is_authenticated", False):
        return {"claimed_items": 0, "merged_items": 0}

    guest_cart = (
        Cart.objects.select_for_update()
        .prefetch_related("items__variant")
        .filter(user__isnull=True, guest_session_key=guest_session_key)
        .first()
    )
    if guest_cart is None:
        return {"claimed_items": 0, "merged_items": 0}

    user_cart = Cart.objects.select_for_update().filter(user=user).first()
    timestamp = timezone.now()
    guest_items = list(guest_cart.items.select_related("variant").order_by("id"))

    if user_cart is None:
        claimed_items = len(guest_items)
        Cart.objects.filter(pk=guest_cart.pk).update(
            user=user,
            guest_session_key=None,
            updated_at=timestamp,
        )
        return {"claimed_items": claimed_items, "merged_items": 0}

    user_items = {
        item.variant_id: item
        for item in user_cart.items.select_related("variant").order_by("id")
    }
    claimed_items = 0
    merged_items = 0

    for guest_item in guest_items:
        existing_item = user_items.get(guest_item.variant_id)
        if existing_item is None:
            CartItem.objects.filter(pk=guest_item.pk).update(
                cart=user_cart,
                unit_price=guest_item.variant.price,
                updated_at=timestamp,
            )
            user_items[guest_item.variant_id] = guest_item
            claimed_items += 1
            continue

        CartItem.objects.filter(pk=existing_item.pk).update(
            quantity=existing_item.quantity + guest_item.quantity,
            unit_price=guest_item.variant.price,
            updated_at=timestamp,
        )
        guest_item.delete()
        merged_items += 1
        claimed_items += 1

    guest_cart.delete()
    return {"claimed_items": claimed_items, "merged_items": merged_items}
