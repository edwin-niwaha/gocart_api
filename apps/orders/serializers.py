from __future__ import annotations

from django.conf import settings
from rest_framework import serializers

from apps.addresses.models import CustomerAddress
from apps.payments.models import Payment
from apps.shipping.models import ShippingMethod
from apps.tenants.utils import user_is_tenant_staff
from .models import Order, OrderItem, OrderStatusEvent


def _validate_order_address_owner(serializer, value: CustomerAddress) -> CustomerAddress:
    request = serializer.context["request"]
    instance = getattr(serializer, "instance", None)
    expected_user = getattr(instance, "user", request.user)

    if value.user_id != expected_user.id:
        raise serializers.ValidationError("Address not found.")

    return value


class OrderItemReadSerializer(serializers.ModelSerializer):
    product_image = serializers.SerializerMethodField()
    line_total = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "tenant",
            "product",
            "product_title",
            "product_image",
            "variant",
            "variant_name",
            "variant_sku",
            "quantity",
            "unit_price",
            "line_total",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_product_image(self, obj):
        product = getattr(obj, "product", None)
        if not product:
            return None
        if product.hero_image:
            return product.hero_image
        if product.image_urls:
            return product.image_urls[0]
        return None


class OrderStatusEventSerializer(serializers.ModelSerializer):
    changed_by_email = serializers.CharField(source="changed_by.email", read_only=True)

    class Meta:
        model = OrderStatusEvent
        fields = (
            "id",
            "from_status",
            "to_status",
            "note",
            "changed_by",
            "changed_by_email",
            "created_at",
        )
        read_only_fields = fields


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    status_events = OrderStatusEventSerializer(many=True, read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    address_id = serializers.IntegerField(source="address.id", read_only=True)
    address_street_name = serializers.CharField(source="address.street_name", read_only=True)
    address_city = serializers.CharField(source="address.city", read_only=True)
    address_region = serializers.CharField(source="address.region", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
            "tenant",
            "slug",
            "user",
            "user_email",
            "status",
            "description",
            "total_price",
            "address_id",
            "address_street_name",
            "address_city",
            "address_region",
            "items",
            "status_events",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderCheckoutSerializer(serializers.Serializer):
    address_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomerAddress.objects.all(),
        source="address",
    )
    description = serializers.CharField(required=False, allow_blank=True)
    shipping_method_id = serializers.PrimaryKeyRelatedField(
        queryset=ShippingMethod.objects.filter(is_active=True),
        source="shipping_method",
        required=False,
        allow_null=True,
    )
    coupon_code = serializers.CharField(
        max_length=50,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )
    payment_method = serializers.ChoiceField(
        choices=[
            Payment.Provider.CASH,
            Payment.Provider.STRIPE,
            Payment.Provider.PAYSTACK,
            Payment.Provider.FLUTTERWAVE,
            Payment.Provider.MTN,
            Payment.Provider.AIRTEL,
        ],
        required=False,
        default=Payment.Provider.CASH,
    )

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        return _validate_order_address_owner(self, value)

    def validate_payment_method(self, value: str) -> str:
        enabled_methods = set(getattr(settings, "ENABLED_CHECKOUT_PAYMENT_METHODS", ["CASH"]))
        if value not in enabled_methods:
            raise serializers.ValidationError("This payment method is not enabled for checkout.")
        return value

    def validate_coupon_code(self, value: str) -> str:
        return value.strip().upper()


class OrderStatusTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OrderWriteSerializer(serializers.ModelSerializer):
    address_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomerAddress.objects.all(),
        source="address",
    )

    class Meta:
        model = Order
        fields = (
            "slug",
            "status",
            "description",
            "address_id",
        )

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        return _validate_order_address_owner(self, value)

    def validate_status(self, value: str) -> str:
        request = self.context["request"]
        if not user_is_tenant_staff(request.user, getattr(request, "tenant", None)):
            raise serializers.ValidationError("Only tenant staff can set order status directly.")
        return value
