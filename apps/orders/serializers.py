from __future__ import annotations

from rest_framework import serializers

from apps.addresses.models import CustomerAddress
from apps.products.models import ProductVariant
from .models import Order, OrderItem, OrderStatusEvent

EDITABLE_ORDER_STATUSES = {Order.Status.PENDING, Order.Status.PROCESSING}


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
        fields = ("id", "from_status", "to_status", "note", "changed_by", "changed_by_email", "created_at")
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
    address_id = serializers.PrimaryKeyRelatedField(queryset=CustomerAddress.objects.all(), source="address")
    description = serializers.CharField(required=False, allow_blank=True)

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You can only use your own address.")
        return value


class OrderStatusTransitionSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Order.Status.choices)
    note = serializers.CharField(max_length=255, required=False, allow_blank=True)


class OrderWriteSerializer(serializers.ModelSerializer):
    address_id = serializers.PrimaryKeyRelatedField(queryset=CustomerAddress.objects.all(), source="address")

    class Meta:
        model = Order
        fields = ("slug", "description", "address_id")

    def validate_slug(self, value: str) -> str:
        instance = getattr(self, "instance", None)
        queryset = Order.objects.filter(slug=value, tenant=self.context["request"].tenant)
        if instance is not None:
            queryset = queryset.exclude(pk=instance.pk)
        if value and queryset.exists():
            raise serializers.ValidationError("An order with this slug already exists for this tenant.")
        return value

    def validate_address_id(self, value: CustomerAddress) -> CustomerAddress:
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You can only use your own address.")
        return value


class OrderItemWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItem
        fields = ("order", "variant", "quantity")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None:
            self.fields["order"].queryset = Order.objects.filter(tenant=tenant)
            self.fields["variant"].queryset = ProductVariant.objects.filter(tenant=tenant, is_active=True)

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs.get("order", getattr(self.instance, "order", None))
        variant = attrs.get("variant", getattr(self.instance, "variant", None))
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", None))

        if order is None or variant is None or quantity is None:
            raise serializers.ValidationError("Order, variant, and quantity are required.")
        if order.tenant_id != request.tenant.id or variant.tenant_id != request.tenant.id:
            raise serializers.ValidationError("Order and variant must belong to the active tenant.")
        if not request.user.is_staff and order.user != request.user:
            raise serializers.ValidationError("You cannot modify another user's order.")
        if order.status not in EDITABLE_ORDER_STATUSES:
            raise serializers.ValidationError(f"Items cannot be modified when order status is {order.get_status_display()}.")
        if not variant.is_active:
            raise serializers.ValidationError("Selected variant is not active.")
        if variant.stock_quantity < quantity:
            raise serializers.ValidationError("Insufficient stock for this variant.")
        max_qty = variant.max_quantity_per_order
        if max_qty is not None and quantity > max_qty:
            raise serializers.ValidationError(f"You can only order up to {max_qty} of this variant.")
        return attrs
