from decimal import Decimal

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
            "tenant",
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
    product_image = serializers.SerializerMethodField()
    unit_price = serializers.ReadOnlyField()
    line_total = serializers.ReadOnlyField()
    is_available = serializers.ReadOnlyField()

    class Meta:
        model = CartItem
        fields = (
            "id",
            "product",
            "product_image",
            "variant",
            "quantity",
            "unit_price",
            "line_total",
            "is_available",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_product_image(self, obj):
        product = getattr(getattr(obj, "variant", None), "product", None)
        return getattr(product, "primary_image", None)


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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None:
            self.fields["variant_id"].queryset = ProductVariant.objects.filter(
                tenant=tenant,
                is_active=True,
                product__is_active=True,
            )

    def validate_quantity(self, value):
        if value < 1:
            raise serializers.ValidationError("Quantity must be at least 1.")
        return value

    def validate(self, attrs):
        variant = attrs.get("variant") or getattr(self.instance, "variant", None)
        quantity = attrs.get("quantity", getattr(self.instance, "quantity", 1))
        tenant = getattr(self.context.get("request"), "tenant", None)

        if variant is None:
            raise serializers.ValidationError({"variant_id": "Variant is required."})

        if tenant is not None and variant.tenant_id != tenant.id:
            raise serializers.ValidationError({"variant_id": "This variant does not belong to the active tenant."})

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
    items = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()
    total_price = serializers.SerializerMethodField()

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

    def _tenant_items(self, obj):
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        queryset = obj.items.select_related(
            "variant",
            "variant__product",
            "variant__product__category",
        )
        if tenant is not None:
            queryset = queryset.filter(variant__tenant=tenant)
        return queryset

    def get_items(self, obj):
        return CartItemReadSerializer(
            self._tenant_items(obj),
            many=True,
            context=self.context,
        ).data

    def get_total_items(self, obj):
        return sum(item.quantity for item in self._tenant_items(obj))

    def get_total_price(self, obj):
        return sum(
            (item.line_total for item in self._tenant_items(obj)),
            Decimal("0.00"),
        )


class CartWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Cart
        fields = ()
