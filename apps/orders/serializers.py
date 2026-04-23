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
    user_email = serializers.SerializerMethodField()
    address_id = serializers.SerializerMethodField()
    address_street_name = serializers.SerializerMethodField()
    address_city = serializers.SerializerMethodField()
    address_region = serializers.SerializerMethodField()
    is_guest = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = (
            "id",
            "tenant",
            "slug",
            "user",
            "user_email",
            "customer_name",
            "customer_email",
            "customer_phone",
            "is_guest",
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

    def get_user_email(self, obj: Order) -> str | None:
        return obj.contact_email or None

    def get_address_id(self, obj: Order) -> int | None:
        return obj.address_id

    def get_address_street_name(self, obj: Order) -> str:
        return obj.delivery_street_name

    def get_address_city(self, obj: Order) -> str:
        return obj.delivery_city

    def get_address_region(self, obj: Order) -> str:
        return obj.delivery_region

    def get_is_guest(self, obj: Order) -> bool:
        return obj.user_id is None


class OrderCheckoutSerializer(serializers.Serializer):
    address_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomerAddress.objects.all(),
        source="address",
        required=False,
        allow_null=True,
    )
    customer_name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    customer_email = serializers.EmailField(required=False, allow_blank=True)
    customer_phone = serializers.CharField(max_length=20, required=False, allow_blank=True)
    street_name = serializers.CharField(
        source="address_street_name",
        max_length=255,
        required=False,
        allow_blank=True,
    )
    city = serializers.CharField(
        source="address_city",
        max_length=100,
        required=False,
        allow_blank=True,
    )
    region = serializers.ChoiceField(
        source="address_region",
        choices=CustomerAddress.Region.choices,
        required=False,
        allow_blank=True,
    )
    additional_information = serializers.CharField(
        source="address_additional_information",
        required=False,
        allow_blank=True,
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

    def validate_customer_name(self, value: str) -> str:
        return value.strip()

    def validate_customer_email(self, value: str) -> str:
        return value.strip().lower()

    def validate_customer_phone(self, value: str) -> str:
        return value.strip()

    def validate_street_name(self, value: str) -> str:
        return value.strip()

    def validate_city(self, value: str) -> str:
        return value.strip()

    def validate_payment_method(self, value: str) -> str:
        enabled_methods = set(
            getattr(settings, "ENABLED_CHECKOUT_PAYMENT_METHODS", ["CASH"])
        )
        if value not in enabled_methods:
            raise serializers.ValidationError(
                "This payment method is not enabled for checkout."
            )
        return value

    def validate_coupon_code(self, value: str) -> str:
        return value.strip().upper()

    def validate(self, attrs):
        request = self.context["request"]
        address = attrs.get("address")

        if getattr(request.user, "is_authenticated", False):
            if address is None:
                raise serializers.ValidationError({"address_id": "Address is required."})

            address = _validate_order_address_owner(self, address)
            attrs["customer_name"] = (
                request.user.get_full_name().strip()
                or request.user.email
                or request.user.username
            )
            attrs["customer_email"] = request.user.email
            attrs["customer_phone"] = address.phone_number
            attrs["address_street_name"] = address.street_name
            attrs["address_city"] = address.city
            attrs["address_region"] = address.region
            attrs["address_additional_information"] = address.additional_information
            return attrs

        errors = {}
        if address is not None:
            errors["address_id"] = "Guest checkout does not support saved addresses."

        required_fields = {
            "customer_name": "customer_name",
            "customer_email": "customer_email",
            "customer_phone": "customer_phone",
            "address_street_name": "street_name",
            "address_city": "city",
            "address_region": "region",
        }
        for attr_name, field_name in required_fields.items():
            if not attrs.get(attr_name):
                errors[field_name] = "This field is required."

        if errors:
            raise serializers.ValidationError(errors)

        return attrs


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

    def validate(self, attrs):
        address = attrs.get("address") or getattr(self.instance, "address", None)
        if address is None:
            raise serializers.ValidationError({"address_id": "Address is required."})
        return attrs

    def validate_status(self, value: str) -> str:
        request = self.context["request"]
        if not user_is_tenant_staff(request.user, getattr(request, "tenant", None)):
            raise serializers.ValidationError(
                "Only tenant staff can set order status directly."
            )
        return value
