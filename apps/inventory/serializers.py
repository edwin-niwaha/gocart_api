from rest_framework import serializers

from .models import Inventory, InventoryMovement


class InventoryMovementSerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="inventory.product.title", read_only=True)

    class Meta:
        model = InventoryMovement
        fields = (
            "id",
            "inventory",
            "product_title",
            "movement_type",
            "quantity",
            "note",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class InventorySerializer(serializers.ModelSerializer):
    product_title = serializers.CharField(source="product.title", read_only=True)
    available_quantity = serializers.ReadOnlyField()

    class Meta:
        model = Inventory
        fields = (
            "id",
            "product",
            "product_title",
            "stock_quantity",
            "reserved_quantity",
            "available_quantity",
            "low_stock_threshold",
            "is_in_stock",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "is_in_stock", "created_at", "updated_at")