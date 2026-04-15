from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import DeviceToken, Notification
from .serializers import DeviceTokenSerializer, NotificationSerializer
from apps.tenants.permissions import IsTenantManager
from apps.tenants.utils import user_is_tenant_staff
from .services import create_notification, mark_all_notifications_read, mark_notification_read


class IsNotificationOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(request.user and (user_is_tenant_staff(request.user, getattr(request, "tenant", None)) or obj.user == request.user))


class NotificationViewSet(viewsets.ModelViewSet):
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated, IsNotificationOwnerOrAdmin]
    http_method_names = ["get", "post", "patch", "delete", "head", "options"]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = Notification.objects.filter(tenant=tenant).order_by("-created_at")
        if user_is_tenant_staff(self.request.user, tenant):
            return queryset
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, tenant=self.request.tenant)

    @action(detail=True, methods=["post"])
    def mark_read(self, request, pk=None):
        notification = mark_notification_read(notification=self.get_object())
        return Response(self.get_serializer(notification).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"])
    def mark_all_read(self, request):
        updated_count = mark_all_notifications_read(user=request.user, tenant=request.tenant)
        return Response(
            {"detail": f"{updated_count} notifications marked as read."},
            status=status.HTTP_200_OK,
        )

    @action(detail=False, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsTenantManager], url_path="broadcast")
    def broadcast(self, request):
        title = str(request.data.get("title", "")).strip()
        message = str(request.data.get("message", "")).strip()
        if not title or not message:
            return Response({"detail": "title and message are required."}, status=status.HTTP_400_BAD_REQUEST)
        users = []
        seen = set()
        for membership in request.tenant.memberships.select_related("user").filter(is_active=True):
            if membership.user_id not in seen:
                seen.add(membership.user_id)
                users.append(membership.user)
        for user in users:
            create_notification(
                user=user, tenant=request.tenant, notification_type=Notification.NotificationType.SYSTEM,
                title=title, message=message, data={"broadcast": True}
            )
        return Response({"detail": f"{len(users)} notifications created."}, status=status.HTTP_201_CREATED)


class DeviceTokenViewSet(viewsets.GenericViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = DeviceTokenSerializer
    queryset = DeviceToken.objects.all()

    def get_queryset(self):
        return DeviceToken.objects.filter(tenant=self.request.tenant)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        token = serializer.save()
        return Response(
            {
                "detail": "Push token registered.",
                "token": token.token,
                "platform": token.platform,
                "tenant": token.tenant.slug,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["post"], url_path="unregister")
    def unregister(self, request, *args, **kwargs):
        token = str(request.data.get("token", "")).strip()
        if not token:
            return Response({"detail": "token is required."}, status=status.HTTP_400_BAD_REQUEST)

        updated = DeviceToken.objects.filter(user=request.user, tenant=request.tenant, token=token).update(is_active=False)
        return Response(
            {
                "detail": "Push token unregistered.",
                "updated": updated,
            },
            status=status.HTTP_200_OK,
        )
