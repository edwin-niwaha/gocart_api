from rest_framework import serializers

from .models import Category, Product, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = (
            "id",
            "tenant",
            "name",
            "slug",
            "image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "tenant", "created_at", "updated_at")
        validators = []


class ProductVariantSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    sku = serializers.CharField(required=False, allow_blank=True)
    is_in_stock = serializers.ReadOnlyField()

    class Meta:
        model = ProductVariant
        fields = (
            "id",
            "tenant",
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
        read_only_fields = (
            "tenant",
            "created_at",
            "updated_at",
            "is_in_stock",
        )
        extra_kwargs = {"sku": {"required": False}}
        validators = []


class ProductSerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        source="category",
        write_only=True,
    )
    variants = ProductVariantSerializer(many=True)
    base_price = serializers.ReadOnlyField()
    is_in_stock = serializers.ReadOnlyField()

    average_rating = serializers.SerializerMethodField()
    total_reviews = serializers.SerializerMethodField()

    class Meta:
        model = Product
        fields = (
            "id",
            "tenant",
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
            "average_rating",
            "total_reviews",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "created_at",
            "updated_at",
            "base_price",
            "is_in_stock",
            "average_rating",
            "total_reviews",
        )
        extra_kwargs = {"slug": {"required": False}}
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        if tenant is not None:
            self.fields["category_id"].queryset = Category.objects.filter(tenant=tenant, is_active=True)

    def get_average_rating(self, obj):
        rating = getattr(obj, "product_rating", None)
        if not rating:
            return "0.00"
        return str(rating.average_rating)

    def get_total_reviews(self, obj):
        rating = getattr(obj, "product_rating", None)
        if not rating:
            return 0
        return rating.total_reviews

    def validate_image_urls(self, value):
        if not isinstance(value, list):
            raise serializers.ValidationError("image_urls must be a list.")
        return value

    def validate_category_id(self, value):
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None and value.tenant_id != tenant.id:
            raise serializers.ValidationError("Category must belong to the active tenant.")
        return value

    def validate_variants(self, value):
        if not value:
            raise serializers.ValidationError("At least one variant is required.")

        seen_names = set()
        seen_skus = set()

        for item in value:
            name = (item.get("name") or "").strip()
            sku = (item.get("sku") or "").strip()

            if not name:
                raise serializers.ValidationError("Each variant must have a name.")

            normalized_name = name.lower()
            if normalized_name in seen_names:
                raise serializers.ValidationError(f"Duplicate variant name: {name}")
            seen_names.add(normalized_name)

            if sku:
                normalized_sku = sku.lower()
                if normalized_sku in seen_skus:
                    raise serializers.ValidationError(f"Duplicate variant sku: {sku}")
                seen_skus.add(normalized_sku)

        return value
