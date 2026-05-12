from rest_framework import serializers

from .models import DeliveryRate, PickupStation, ShippingMethod


class ShippingMethodReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = (
            "id",
            "name",
            "description",
            "fee",
            "estimated_days",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ShippingMethodWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShippingMethod
        fields = (
            "name",
            "description",
            "fee",
            "estimated_days",
            "is_active",
        )


class PickupStationReadSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupStation
        fields = (
            "id",
            "name",
            "city",
            "area",
            "address",
            "phone",
            "opening_hours",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PickupStationWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = PickupStation
        fields = (
            "name",
            "city",
            "area",
            "address",
            "phone",
            "opening_hours",
            "is_active",
        )


class DeliveryRateReadSerializer(serializers.ModelSerializer):
    region_label = serializers.CharField(source="get_region_display", read_only=True)

    class Meta:
        model = DeliveryRate
        fields = (
            "id",
            "tenant",
            "region",
            "region_label",
            "city",
            "area",
            "fee",
            "estimated_days",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class DeliveryRateWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeliveryRate
        fields = (
            "region",
            "city",
            "area",
            "fee",
            "estimated_days",
            "is_active",
        )

    def validate_city(self, value: str) -> str:
        return value.strip()

    def validate_area(self, value: str) -> str:
        return value.strip()


