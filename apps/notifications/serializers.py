from rest_framework import serializers

from .models import Notification, DeviceToken


class NotificationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notification
        fields = (
            "id",
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
            "user",
            "read_at",
            "created_at",
            "updated_at",
        )


class DeviceTokenSerializer(serializers.ModelSerializer):
    class Meta:
        model = DeviceToken
        fields = ("token", "platform", "device_id", "app_version")

    def create(self, validated_data):
        user = self.context["request"].user

        obj, _ = DeviceToken.objects.update_or_create(
            token=validated_data["token"],
            defaults={
                "user": user,
                "platform": validated_data["platform"],
                "device_id": validated_data.get("device_id", ""),
                "app_version": validated_data.get("app_version", ""),
                "is_active": True,
            },
        )
        return obj