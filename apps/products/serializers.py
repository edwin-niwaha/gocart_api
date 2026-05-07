from rest_framework import serializers

from .models import Category, Product, ProductImage, ProductVariant


class CategorySerializer(serializers.ModelSerializer):
    slug = serializers.CharField(required=False, allow_blank=True)
    image_url = serializers.ReadOnlyField()

    class Meta:
        model = Category
        fields = (
            "id",
            "tenant",
            "name",
            "slug",
            "image",
            "image_url",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "tenant", "image_url", "created_at", "updated_at")
        validators = []


class ProductImageSerializer(serializers.ModelSerializer):
    id = serializers.IntegerField(required=False)
    image = serializers.ImageField(required=False)
    image_url = serializers.ReadOnlyField()

    class Meta:
        model = ProductImage
        fields = (
            "id",
            "tenant",
            "image",
            "image_url",
            "alt_text",
            "sort_order",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "image_url", "created_at", "updated_at")
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
    primary_image = serializers.ReadOnlyField()
    hero_image_url = serializers.ReadOnlyField()

    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.filter(is_active=True),
        source="category",
        write_only=True,
    )

    images = ProductImageSerializer(many=True, required=False)
    variants = ProductVariantSerializer(many=True, required=False)

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
            "hero_image_url",
            "primary_image",
            "is_active",
            "is_featured",
            "base_price",
            "is_in_stock",
            "category",
            "category_id",
            "images",
            "variants",
            "average_rating",
            "total_reviews",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "hero_image_url",
            "primary_image",
            "created_at",
            "updated_at",
            "base_price",
            "is_in_stock",
            "average_rating",
            "total_reviews",
        )
        extra_kwargs = {
            "slug": {"required": False},
            "description": {"required": False, "allow_blank": True},
        }
        validators = []

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)

        if tenant is not None:
            self.fields["category_id"].queryset = Category.objects.filter(
                tenant=tenant,
                is_active=True,
            )

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

    def validate_category_id(self, value):
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None and value.tenant_id != tenant.id:
            raise serializers.ValidationError("Category must belong to the active tenant.")
        return value

    def validate_images(self, value):
        seen_sort_orders = set()

        for item in value:
            if not item.get("id") and not item.get("image"):
                raise serializers.ValidationError("New product images must include an image file.")

            sort_order = item.get("sort_order", 0)
            if sort_order in seen_sort_orders:
                raise serializers.ValidationError(f"Duplicate image sort_order: {sort_order}")
            seen_sort_orders.add(sort_order)

        return value

    def validate_variants(self, value):
        if not value:
            return value

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
