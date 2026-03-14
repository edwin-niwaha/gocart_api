from rest_framework import serializers

from .models import Order, OrderItem


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
            "items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OrderWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Order
        fields = (
            "slug",
            "description",
        )

    def validate_slug(self, value):
        if value and Order.objects.filter(slug=value).exists():
            raise serializers.ValidationError("An order with this slug already exists.")
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
        order = attrs["order"]
        variant = attrs["variant"]

        if not request.user.is_staff and order.user != request.user:
            raise serializers.ValidationError("You cannot modify another user's order.")

        if variant.product_id is None:
            raise serializers.ValidationError("Selected variant is invalid.")

        if not variant.is_active:
            raise serializers.ValidationError("Selected variant is not active.")

        if variant.stock_quantity < attrs["quantity"]:
            raise serializers.ValidationError("Insufficient stock for this variant.")

        max_qty = variant.max_quantity_per_order
        if max_qty is not None and attrs["quantity"] > max_qty:
            raise serializers.ValidationError(
                f"You can only order up to {max_qty} of this variant."
            )

        return attrs