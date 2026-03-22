from rest_framework import serializers

from apps.orders.models import Order
from .models import Payment
from apps.addresses.models import CustomerAddress


# class MTNInitiatePaymentSerializer(serializers.Serializer):
#     order = serializers.IntegerField()
#     phone_number = serializers.CharField(max_length=20)

#     def validate_phone_number(self, value: str) -> str:
#         raw = value.strip().replace(" ", "")

#         if raw.startswith("+256"):
#             normalized = raw
#         elif raw.startswith("256"):
#             normalized = f"+{raw}"
#         elif raw.startswith("0"):
#             normalized = f"+256{raw[1:]}"
#         else:
#             normalized = raw

#         if not normalized.startswith("+2567") or len(normalized) != 13:
#             raise serializers.ValidationError(
#                 "Enter a valid Uganda number like 078XXXXXXX or +25678XXXXXXX."
#             )

#         return normalized

#     def validate_order(self, value: int) -> int:
#         request = self.context["request"]

#         try:
#             order = Order.objects.get(id=value, user=request.user)
#         except Order.DoesNotExist:
#             raise serializers.ValidationError("Order not found.")

#         self.context["order_instance"] = order
#         return value

class MTNInitiatePaymentSerializer(serializers.Serializer):
    address_id = serializers.IntegerField()
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

    def validate_address_id(self, value: int) -> int:
        request = self.context["request"]

        try:
          address = CustomerAddress.objects.get(id=value, user=request.user)
        except CustomerAddress.DoesNotExist:
          raise serializers.ValidationError("Address not found.")

        self.context["address_instance"] = address
        return value
    
    
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