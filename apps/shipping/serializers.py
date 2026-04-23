from rest_framework import serializers

from apps.addresses.models import CustomerAddress
from apps.orders.models import Order
from apps.tenants.utils import user_is_tenant_staff
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

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        request = self.context.get("request")
        tenant = getattr(request, "tenant", None)
        user = getattr(request, "user", None)

        if tenant is None or user is None:
            return

        order_queryset = Order.objects.filter(tenant=tenant)
        if not user_is_tenant_staff(user, tenant):
            order_queryset = order_queryset.filter(user=user)

        self.fields["order"].queryset = order_queryset
        self.fields["address"].queryset = CustomerAddress.objects.select_related("user")

    def validate(self, attrs):
        request = self.context["request"]
        order = attrs["order"]
        address = attrs["address"]
        tenant = getattr(request, "tenant", None)
        is_tenant_staff = user_is_tenant_staff(request.user, tenant)

        if tenant is None or order.tenant_id != tenant.id:
            raise serializers.ValidationError("Order not found.")

        if not is_tenant_staff and order.user != request.user:
            raise serializers.ValidationError("You cannot create a shipment for another user's order.")

        if address.user_id != order.user_id:
            raise serializers.ValidationError("You cannot use another user's address.")

        return attrs
