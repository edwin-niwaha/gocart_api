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
    items = serializers.SerializerMethodField()
    total_items = serializers.SerializerMethodField()

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

    def _tenant_items(self, obj):
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        queryset = obj.items.select_related("product", "product__category")
        if tenant is not None:
            queryset = queryset.filter(product__tenant=tenant)
        return queryset

    def get_items(self, obj):
        return WishlistItemReadSerializer(
            self._tenant_items(obj),
            many=True,
            context=self.context,
        ).data

    def get_total_items(self, obj):
        return self._tenant_items(obj).count()


class WishlistWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Wishlist
        fields = ()
