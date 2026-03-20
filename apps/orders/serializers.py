from __future__ import annotations

from rest_framework import serializers

from apps.addresses.models import CustomerAddress
from .models import Order, OrderItem


EDITABLE_ORDER_STATUSES = {
    Order.Status.PENDING,
    Order.Status.PROCESSING,
}


class OrderItemReadSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    variant_name = serializers.CharField(read_only=True)
    variant_sku = serializers.CharField(read_only=True)
    line_total = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_title",
            "product_slug",
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


class OrderReadSerializer(serializers.ModelSerializer):
    items = OrderItemReadSerializer(many=True, read_only=True)
    user_email = serializers.CharField(source="user.email", read_only=True)
    address_id = serializers.IntegerField(source="address.id", read_only=True)
    address_street_name = serializers.CharField(source="address.street_name", read_only=True)
    address_city = serializers.CharField(source="address.city", read_only=True)
    address_region = serializers.CharField(source="address.region", read_only=True)

    class Meta:
        model = Order
        fields = (
            "id",
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

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You can only use your own address.")
        return value


class OrderWriteSerializer(serializers.ModelSerializer):
    address_id = serializers.PrimaryKeyRelatedField(
        queryset=CustomerAddress.objects.all(),
        source="address",
    )

    class Meta:
        model = Order
        fields = (
            "slug",
            "description",
            "address_id",
        )

    def validate_slug(self, value: str) -> str:
        instance = getattr(self, "instance", None)
        queryset = Order.objects.filter(slug=value)
        if instance is not None:
            queryset = queryset.exclude(pk=instance.pk)

        if value and queryset.exists():
            raise serializers.ValidationError("An order with this slug already exists.")
        return value

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You can only use your own address.")
        return value


class OrderItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = (
            "order",
            "variant",
            "quantity",
        )

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs.get("order", getattr(self.instance, "order", None))
        variant = attrs.get("variant", getattr(self.instance, "variant", None))
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", None))

        if order is None or variant is None or quantity is None:
            raise serializers.ValidationError("Order, variant, and quantity are required.")

        if not request.user.is_staff and order.user != request.user:
            raise serializers.ValidationError("You cannot modify another user's order.")

        if order.status not in EDITABLE_ORDER_STATUSES:
            raise serializers.ValidationError(
                f"Items cannot be modified when order status is {order.get_status_display()}."
            )

        if not variant.is_active:
            raise serializers.ValidationError("Selected variant is not active.")

        if variant.stock_quantity < quantity:
            raise serializers.ValidationError("Insufficient stock for this variant.")

        max_qty = variant.max_quantity_per_order
        if max_qty is not None and quantity > max_qty:
            raise serializers.ValidationError(
                f"You can only order up to {max_qty} of this variant."
            )

        return attrs