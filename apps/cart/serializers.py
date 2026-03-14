from rest_framework import serializers

from apps.products.models import ProductVariant
from apps.products.serializers import ProductSerializer
from .models import Cart, CartItem


class ProductVariantSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "product",
            "name",
            "sku",
            "price",
            "stock_quantity",
            "max_quantity_per_order",
            "is_active",
            "sort_order",
        )
        read_only_fields = fields


class CartItemReadSerializer(serializers.ModelSerializer):
    variant = ProductVariantSerializer(read_only=True)
    product = ProductSerializer(source="variant.product", read_only=True)
    unit_price = serializers.ReadOnlyField()
    line_total = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "variant",
            "quantity",
            "unit_price",
            "line_total",
            "is_available",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CartItemWriteSerializer(serializers.ModelSerializer):
    variant_id = serializers.PrimaryKeyRelatedField(
        queryset=ProductVariant.objects.filter(
            is_active=True,
            product__is_active=True,
        ),
        source="variant",
    )

    class Meta:
        model = CartItem
        fields = (
            "variant_id",
            "quantity",
        )

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, attrs):
        variant = attrs.get("variant") or getattr(self.instance, "variant", None)
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", 1))

        if variant is None:
            raise serializers.ValidationError({"variant_id": "Variant is required."})

        if not variant.is_active:
            raise serializers.ValidationError({"variant_id": "This variant is inactive."})

        if not variant.product.is_active:
            raise serializers.ValidationError({"variant_id": "This product is inactive."})

        if quantity > variant.stock_quantity:
            raise serializers.ValidationError(
                {"quantity": f"Only {variant.stock_quantity} items available in stock."}
            )

        if (
            variant.max_quantity_per_order is not None
            and quantity > variant.max_quantity_per_order
        ):
            raise serializers.ValidationError(
                {
                    "quantity": (
                        f"Maximum allowed quantity is "
                        f"{variant.max_quantity_per_order} for this item."
                    )
                }
            )

        return attrs


class CartReadSerializer(serializers.ModelSerializer):
    items = CartItemReadSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()
    total_price = serializers.ReadOnlyField()

    class Meta:
        model = Cart
        fields = (
            "id",
            "user",
            "items",
            "total_items",
            "total_price",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class CartWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = ()