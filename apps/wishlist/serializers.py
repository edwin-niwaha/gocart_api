from rest_framework import serializers

from apps.products.models import Product
from apps.products.serializers import ProductSerializer
from .models import Wishlist, WishlistItem


class WishlistItemReadSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)

    class Meta:
        model = WishlistItem
        fields = (
            "id",
            "product",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class WishlistItemWriteSerializer(serializers.ModelSerializer):
    product_id = serializers.PrimaryKeyRelatedField(
        queryset=Product.objects.filter(is_active=True),
        source="product",
    )

    class Meta:
        model = WishlistItem
        fields = ("product_id",)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        tenant = getattr(self.context.get("request"), "tenant", None)
        if tenant is not None:
            self.fields["product_id"].queryset = Product.objects.filter(tenant=tenant, is_active=True)


class WishlistReadSerializer(serializers.ModelSerializer):
    items = WishlistItemReadSerializer(many=True, read_only=True)
    total_items = serializers.ReadOnlyField()

    class Meta:
        model = Wishlist
        fields = (
            "id",
            "user",
            "items",
            "total_items",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class WishlistWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        fields = ()
