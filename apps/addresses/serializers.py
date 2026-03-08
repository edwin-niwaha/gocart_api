from rest_framework import serializers

from .models import CustomerAddress


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            "id",
            "label",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "phone_number",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate(self, attrs):
        postal_code = attrs.get("postal_code")
        if postal_code and not postal_code.strip():
            raise serializers.ValidationError(
                {"postal_code": "Postal code cannot be empty."}
            )
        return attrs