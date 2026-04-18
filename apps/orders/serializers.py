from __future__ import annotations

from rest_framework import serializers

from apps.addresses.models import CustomerAddress
from apps.payments.models import Payment
from .models import Order, OrderItem, OrderStatusEvent


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
    payment_method = serializers.ChoiceField(
        choices=[
            Payment.Provider.CASH,
            Payment.Provider.MTN,
            Payment.Provider.AIRTEL,
        ],
        required=False,
        default=Payment.Provider.CASH,
    )

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You can only use your own address.")
        return value


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
        fields = ("slug", "description", "address_id")

    def validate_slug(self, value: str) -> str:
        instance = getattr(self, "instance", None)
        queryset = Order.objects.filter(
            slug=value,
            tenant=self.context["request"].tenant,
        )
        if instance is not None:
            queryset = queryset.exclude(pk=instance.pk)
        if value and queryset.exists():
            raise serializers.ValidationError(
                "An order with this slug already exists for this tenant."
            )
        return value

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You can only use your own address.")
        return value