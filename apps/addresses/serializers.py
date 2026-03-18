from rest_framework import serializers

from .models import CustomerAddress


class CustomerAddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomerAddress
        fields = (
            "id",
            "street_name",
            "city",
            "phone_number",
            "additional_telephone",
            "additional_information",
            "region",
            "is_default",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "created_at",
            "updated_at",
        )

    def validate_street_name(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Street name cannot be empty.")
        return value

    def validate_city(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("City cannot be empty.")
        return value

    def validate(self, attrs):
        phone_number = attrs.get("phone_number")
        additional_telephone = attrs.get("additional_telephone")

        if phone_number and additional_telephone and phone_number == additional_telephone:
            raise serializers.ValidationError(
                {"additional_telephone": "Additional telephone must be different from phone number."}
            )

        return attrs