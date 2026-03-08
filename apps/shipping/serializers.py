from rest_framework import serializers

from .models import Shipment, ShippingMethod


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


class ShipmentReadSerializer(serializers.ModelSerializer):
    order_slug = serializers.CharField(source="order.slug", read_only=True)
    user_email = serializers.CharField(source="order.user.email", read_only=True)
    shipping_method_name = serializers.CharField(source="shipping_method.name", read_only=True)

    class Meta:
        model = Shipment
        fields = (
            "id",
            "order",
            "order_slug",
            "user_email",
            "address",
            "shipping_method",
            "shipping_method_name",
            "status",
            "tracking_number",
            "shipping_fee",
            "dispatched_at",
            "delivered_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class ShipmentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shipment
        fields = (
            "order",
            "address",
            "shipping_method",
        )

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]
        address = attrs["address"]

        if not request.user.is_staff and order.user != request.user:
            raise serializers.ValidationError("You cannot create a shipment for another user's order.")

        if not request.user.is_staff and address.user != request.user:
            raise serializers.ValidationError("You cannot use another user's address.")

        return attrs