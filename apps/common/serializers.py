from django.utils import timezone
from rest_framework import serializers

from .models import AuditLog, SupportMessage


class ContactMessageSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=120)
    email = serializers.EmailField()
    subject = serializers.CharField(max_length=255, required=False, allow_blank=True)
    message = serializers.CharField(max_length=5000)

class NewsletterSubscribeSerializer(serializers.Serializer):
    email = serializers.EmailField()

    
class SupportMessageSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = (
            "id",
            "tenant",
            "user",
            "name",
            "email",
            "subject",
            "message",
            "status",
            "assigned_to",
            "resolved_at",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("tenant", "user", "resolved_at", "created_at", "updated_at")


class SupportMessageUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = SupportMessage
        fields = ("status", "assigned_to")

    def validate_assigned_to(self, value):
        request = self.context["request"]
        tenant = getattr(request, "tenant", None)
        if value and not value.tenant_memberships.filter(tenant=tenant, is_active=True).exists():
            raise serializers.ValidationError("Assigned user must belong to the active tenant.")
        return value

    def update(self, instance, validated_data):
        status_value = validated_data.get("status", instance.status)
        instance.assigned_to = validated_data.get("assigned_to", instance.assigned_to)
        instance.status = status_value
        if status_value == SupportMessage.Status.RESOLVED and instance.resolved_at is None:
            instance.resolved_at = timezone.now()
        elif status_value != SupportMessage.Status.RESOLVED:
            instance.resolved_at = None
        instance.save(update_fields=["assigned_to", "status", "resolved_at", "updated_at"])
        return instance


class AuditLogSerializer(serializers.ModelSerializer):
    actor_email = serializers.CharField(source="actor.email", read_only=True)

    class Meta:
        model = AuditLog
        fields = (
            "id",
            "tenant",
            "actor",
            "actor_email",
            "action",
            "target_type",
            "target_id",
            "summary",
            "metadata",
            "created_at",
        )
        read_only_fields = fields
