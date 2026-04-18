from rest_framework import serializers

from apps.addresses.models import CustomerAddress
from apps.orders.models import Order

from .models import Payment


class PaymentCreateSerializer(serializers.ModelSerializer):
    order = serializers.PrimaryKeyRelatedField(
        queryset=Order.objects.all()
    )

    class Meta:
        model = Payment
        fields = [
            "order",
            "provider",
            "amount",
            "currency",
            "phone_number",
        ]

    def validate_order(self, value):
        request = self.context["request"]

        if value.user != request.user:
            raise serializers.ValidationError("Order not found.")

        return value

    def create(self, validated_data):
        request = self.context["request"]

        return Payment.objects.create(
            tenant=getattr(request, "tenant", None),
            user=request.user,
            status=Payment.Status.PENDING,
            **validated_data,
        )


class MTNInitiatePaymentSerializer(serializers.Serializer):
    address_id = serializers.IntegerField(required=False)
    order = serializers.IntegerField(required=False)
    phone_number = serializers.CharField(max_length=20)

    def validate_phone_number(self, value: str) -> str:
        raw = value.strip().replace(" ", "")

        if raw.startswith("+256"):
            normalized = raw
        elif raw.startswith("256"):
            normalized = f"+{raw}"
        elif raw.startswith("0"):
            normalized = f"+256{raw[1:]}"
        else:
            normalized = raw

        if not normalized.startswith("+2567") or len(normalized) != 13:
            raise serializers.ValidationError(
                "Enter a valid Uganda number like 078XXXXXXX or +25678XXXXXXX."
            )

        return normalized

    def validate(self, attrs):
        request = self.context["request"]
        address_id = attrs.get("address_id")
        order_id = attrs.get("order")

        if not address_id and not order_id:
            raise serializers.ValidationError(
                {"detail": "Either address_id or order is required."}
            )

        if address_id:
            try:
                address = CustomerAddress.objects.get(
                    id=address_id,
                    user=request.user,
                )
            except CustomerAddress.DoesNotExist:
                raise serializers.ValidationError(
                    {"address_id": "Address not found."}
                )

            self.context["address_instance"] = address
            return attrs

        try:
            order = Order.objects.select_related("address").get(
                id=order_id,
                user=request.user,
            )
        except Order.DoesNotExist:
            raise serializers.ValidationError({"order": "Order not found."})

        self.context["order_instance"] = order

        address = getattr(order, "address", None)
        if address is None:
            raise serializers.ValidationError(
                {"detail": "This order does not have a delivery address."}
            )

        self.context["address_instance"] = address
        attrs["address_id"] = address.id
        return attrs


class PaymentStatusSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "reference",
            "provider",
            "status",
            "amount",
            "currency",
            "phone_number",
            "external_id",
            "transaction_id",
            "provider_response",
            "paid_at",
            "created_at",
            "updated_at",
        ]


class PaymentListSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    order_slug = serializers.CharField(source="order.slug", read_only=True)

    class Meta:
        model = Payment
        fields = [
            "id",
            "user",
            "user_email",
            "order",
            "order_slug",
            "provider",
            "status",
            "currency",
            "amount",
            "phone_number",
            "reference",
            "external_id",
            "transaction_id",
            "checkout_url",
            "provider_response",
            "paid_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields