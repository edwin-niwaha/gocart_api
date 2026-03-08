from rest_framework import serializers

from .models import Order, OrderItem


class OrderItemReadSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    product_slug = serializers.CharField(source="product.slug", read_only=True)
    line_total = serializers.ReadOnlyField()

    class Meta:
        model = OrderItem
        fields = (
            "id",
            "product",
            "product_title",
            "product_slug",
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
            "product",
            "quantity",
        )

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]

        if not request.user.is_staff and order.user != request.user:
            raise serializers.ValidationError("You cannot modify another user's order.")

        return attrs