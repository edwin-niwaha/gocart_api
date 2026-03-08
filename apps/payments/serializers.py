from rest_framework import serializers

from .models import Payment


class PaymentReadSerializer(serializers.ModelSerializer):
    user_email = serializers.CharField(source="user.email", read_only=True)
    order_slug = serializers.CharField(source="order.slug", read_only=True)

    class Meta:
        model = Payment
        fields = (
            "id",
            "user",
            "user_email",
            "order",
            "order_slug",
            "provider",
            "status",
            "currency",
            "amount",
            "reference",
            "transaction_id",
            "checkout_url",
            "provider_response",
            "paid_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class PaymentWriteSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = (
            "order",
            "provider",
            "currency",
            "amount",
        )

    def validate_order(self, value):
        request = self.context["request"]
        if not request.user.is_staff and value.user != request.user:
            raise serializers.ValidationError("You cannot create a payment for another user's order.")
        return value

    def validate(self, attrs):
        order = attrs["order"]
        amount = attrs["amount"]

        if amount <= 0:
            raise serializers.ValidationError({"amount": "Amount must be greater than zero."})

        if amount > order.total_price:
            raise serializers.ValidationError({"amount": "Amount cannot exceed the order total."})

        return attrs