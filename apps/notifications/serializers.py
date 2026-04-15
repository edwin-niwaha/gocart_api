from rest_framework import serializers

from .models import DeviceToken, Notification


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
            "tenant",
            "user",
            "notification_type",
            "title",
            "message",
            "data",
            "is_read",
            "read_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "tenant",
            "user",
            "read_at",
            "created_at",
            "updated_at",
        )


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ("token", "platform", "device_id", "app_version")

    def validate_token(self, value: str) -> str:
        token = value.strip()
        if not token:
            raise serializers.ValidationError("token is required.")
        return token

    def create(self, validated_data):
        user = self.context["request"].user
        tenant = self.context["request"].tenant
        token = validated_data["token"]

        obj, _ = DeviceToken.objects.update_or_create(
            token=token,
            defaults={
                "tenant": tenant,
                "user": user,
                "platform": validated_data["platform"],
                "device_id": validated_data.get("device_id", ""),
                "app_version": validated_data.get("app_version", ""),
                "is_active": True,
            },
        )
        return obj
