from typing import cast

from django.utils import timezone
from rest_framework.decorators import action
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from apps.tenants.permissions import IsTenantStaff
from .models import AuditLog, SupportMessage, NewsletterSubscriber
from .serializers import (
    AuditLogSerializer,
    ContactMessageSerializer,
    SupportMessageSerializer,
    SupportMessageUpdateSerializer,
    NewsletterSubscribeSerializer
)
from .tasks import (
    send_contact_email_task,
    send_newsletter_confirmation_request_task,
    send_newsletter_subscription_confirmed_task
)


def create_audit_log(*, tenant, actor, action: str, summary: str, target=None, metadata: dict | None = None):
    return AuditLog.objects.create(
        tenant=tenant,
        actor=actor,
        action=action,
        target_type=target.__class__.__name__ if target is not None else "",
        target_id=str(getattr(target, "pk", "")) if target is not None else "",
        summary=summary,
        metadata=metadata or {},
    )


class ContactMessageViewSet(viewsets.ViewSet):
    permission_classes = [permissions.AllowAny]

    def create(self, request):
        serializer = ContactMessageSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = cast(dict[str, str], serializer.validated_data)
        support_message = SupportMessage.objects.create(
            tenant=getattr(request, "tenant", None),
            user=request.user if getattr(request.user, "is_authenticated", False) else None,
            name=validated_data["name"],
            email=validated_data["email"],
            subject=validated_data.get("subject", ""),
            message=validated_data["message"],
        )

        send_contact_email_task.delay(
            name=validated_data["name"],
            email=validated_data["email"],
            message=validated_data["message"],
            subject=validated_data.get("subject", ""),
            tenant_slug=support_message.tenant.slug if support_message.tenant_id else "",
        )

        create_audit_log(
            tenant=support_message.tenant,
            actor=support_message.user,
            action="support_message.created",
            summary=f"Support message created by {support_message.email}",
            target=support_message,
        )

        return Response({"detail": "Message queued successfully.", "id": support_message.id}, status=status.HTTP_201_CREATED)


class SupportMessageViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTenantStaff]

    def get_queryset(self):
        return SupportMessage.objects.filter(tenant=self.request.tenant).select_related("tenant", "user", "assigned_to")

    def get_serializer_class(self):
        if self.action in {"update", "partial_update"}:
            return SupportMessageUpdateSerializer
        return SupportMessageSerializer

    def perform_update(self, serializer):
        support_message = serializer.save()
        create_audit_log(
            tenant=self.request.tenant,
            actor=self.request.user,
            action="support_message.updated",
            summary=f"Support message {support_message.id} updated",
            target=support_message,
            metadata={"status": support_message.status},
        )


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTenantStaff]
    serializer_class = AuditLogSerializer

    def get_queryset(self):
        return AuditLog.objects.filter(tenant=self.request.tenant).select_related("actor")



class NewsletterSubscribeViewSet(viewsets.ViewSet):
    permission_classes = [AllowAny]

    def create(self, request):
        serializer = NewsletterSubscribeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        validated_data = cast(dict[str, str], serializer.validated_data)
        email = validated_data["email"].strip().lower()
        tenant = getattr(request, "tenant", None)

        subscriber, created = NewsletterSubscriber.objects.get_or_create(
            email=email,
            tenant=tenant,
            defaults={
                "is_active": False,
                "is_confirmed": False,
            },
        )

        if subscriber.is_confirmed and subscriber.is_active:
            return Response(
                {"detail": "This email is already subscribed."},
                status=status.HTTP_200_OK,
            )

        if not created:
            subscriber.is_active = False
            subscriber.is_confirmed = False
            subscriber.confirmed_at = None
            subscriber.save(update_fields=["is_active", "is_confirmed", "confirmed_at"])

        send_newsletter_confirmation_request_task.delay(subscriber.id)

        return Response(
            {"detail": "Check your email to confirm your subscription."},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="confirm")
    def confirm(self, request):
        token = (request.query_params.get("token") or "").strip()

        if not token:
            return Response(
                {"detail": "Missing confirmation token."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            subscriber = NewsletterSubscriber.objects.get(confirmation_token=token)
        except NewsletterSubscriber.DoesNotExist:
            return Response(
                {"detail": "Invalid or expired confirmation link."},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not subscriber.is_confirmed:
            subscriber.is_confirmed = True
            subscriber.is_active = True
            subscriber.confirmed_at = timezone.now()
            subscriber.save(update_fields=["is_confirmed", "is_active", "confirmed_at"])

            send_newsletter_subscription_confirmed_task.delay(subscriber.id)

        return Response(
            {"detail": "Your subscription has been confirmed."},
            status=status.HTTP_200_OK,
        )