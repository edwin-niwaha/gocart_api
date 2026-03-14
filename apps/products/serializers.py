from rest_framework import serializers

from .models import Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id",
            "name",
            "slug",
            "image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ProductVariantSerializer(serializers.ModelSerializer):
    is_in_stock = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "name",
            "sku",
            "price",
            "stock_quantity",
            "max_quantity_per_order",
            "is_active",
            "sort_order",
            "is_in_stock",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "is_in_stock")


class ProductSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        source="category",
        write_only=True,
    )
    variants = ProductVariantSerializer(many=True)
    base_price = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()

    class Meta:
        model = Product
        fields = (
            "id",
            "title",
            "slug",
            "description",
            "hero_image",
            "image_urls",
            "is_active",
            "is_featured",
            "base_price",
            "is_in_stock",
            "category",
            "category_id",
            "variants",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
            "base_price",
            "is_in_stock",
        )

    def validate_image_urls(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("image_urls must be a list.")
        return value

    def validate_variants(self, value):
        if not value:
            raise serializers.ValidationError("At least one variant is required.")

        seen_names = set()
        seen_skus = set()

        for item in value:
            name = item.get("name")
            sku = item.get("sku")

            if not name:
                raise serializers.ValidationError("Each variant must have a name.")

            if name in seen_names:
                raise serializers.ValidationError(f"Duplicate variant name: {name}")
            seen_names.add(name)

            if sku:
                if sku in seen_skus:
                    raise serializers.ValidationError(f"Duplicate variant sku: {sku}")
                seen_skus.add(sku)

        return value