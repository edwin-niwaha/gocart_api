from decimal import Decimal

from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import Coupon


def get_valid_coupon(*, code: str) -> Coupon:
    normalized_code = code.strip().upper()

    try:
        coupon = Coupon.objects.prefetch_related("products", "categories").get(code=normalized_code)
    except Coupon.DoesNotExist as exc:
        raise ValidationError("Invalid coupon code.") from exc

    now = timezone.now()

    if not coupon.is_active:
        raise ValidationError("Coupon is inactive.")

    if coupon.starts_at > now:
        raise ValidationError("Coupon is not active yet.")

    if coupon.ends_at < now:
        raise ValidationError("Coupon has expired.")

    if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
        raise ValidationError("Coupon usage limit has been reached.")

    return coupon


def validate_coupon_for_amount(*, coupon: Coupon, amount: Decimal) -> None:
    if amount < coupon.min_order_amount:
        raise ValidationError("Order amount does not meet the coupon minimum.")


def validate_coupon_for_order(*, coupon: Coupon, order) -> None:
    validate_coupon_for_amount(coupon=coupon, amount=order.total_price)

    if coupon.products.exists() or coupon.categories.exists():
        order_product_ids = set(order.items.values_list("product_id", flat=True))
        order_category_ids = set(
            order.items.values_list("product__category_id", flat=True)
        )

        coupon_product_ids = set(coupon.products.values_list("id", flat=True))
        coupon_category_ids = set(coupon.categories.values_list("id", flat=True))

        product_match = bool(order_product_ids & coupon_product_ids)
        category_match = bool(order_category_ids & coupon_category_ids)

        if not product_match and not category_match:
            raise ValidationError("Coupon does not apply to this order.")


def calculate_coupon_discount(*, coupon: Coupon, amount: Decimal) -> Decimal:
    validate_coupon_for_amount(coupon=coupon, amount=amount)

    if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
        discount = (amount * coupon.value) / Decimal("100.00")
        if coupon.max_discount_amount:
            discount = min(discount, coupon.max_discount_amount)
    else:
        discount = coupon.value

    return min(discount, amount)


def apply_coupon_to_order(*, order, code: str) -> dict:
    coupon = get_valid_coupon(code=code)
    validate_coupon_for_order(coupon=coupon, order=order)

    discount = calculate_coupon_discount(coupon=coupon, amount=order.total_price)
    final_amount = max(order.total_price - discount, Decimal("0.00"))

    return {
        "coupon": coupon,
        "discount": discount,
        "final_amount": final_amount,
    }


def increment_coupon_usage(*, coupon: Coupon) -> Coupon:
    coupon.used_count += 1
    coupon.save(update_fields=["used_count", "updated_at"])
    return coupon