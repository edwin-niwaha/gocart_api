from django.contrib.auth import get_user_model
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Tenant, TenantBranding, TenantFeatureFlag, TenantMembership, TenantSettings
from .permissions import IsTenantAdmin, ROLE_ORDER, get_user_tenant_role, is_platform_admin
from .serializers import (
    TenantBrandingSerializer,
    TenantFeatureFlagSerializer,
    TenantFeatureFlagWriteSerializer,
    TenantMembershipSerializer,
    TenantMembershipUpdateSerializer,
    TenantMembershipWriteSerializer,
    TenantSerializer,
    TenantSettingsSerializer,
)
from .services import get_default_tenant

User = get_user_model()


class TenantViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = TenantSerializer
    permission_classes = [permissions.AllowAny]
    lookup_field = "slug"

    def get_queryset(self):
        queryset = Tenant.objects.filter(is_active=True).select_related("branding", "settings").prefetch_related("feature_flags")
        if is_platform_admin(self.request.user):
            return Tenant.objects.all().select_related("branding", "settings").prefetch_related("feature_flags")
        return queryset

    @action(detail=False, methods=["get"], url_path="current")
    def current(self, request, *args, **kwargs):
        tenant = getattr(request, "tenant", None) or get_default_tenant()
        return Response(self.get_serializer(tenant).data)


class CurrentTenantBrandingView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        branding, _ = TenantBranding.objects.get_or_create(tenant=tenant, defaults={"app_name": tenant.name})
        return Response(TenantBrandingSerializer(branding).data)

    def patch(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and IsTenantAdmin().has_permission(request, self)):
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        branding, _ = TenantBranding.objects.get_or_create(tenant=request.tenant, defaults={"app_name": request.tenant.name})
        serializer = TenantBrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CurrentTenantSettingsView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        return Response(TenantSettingsSerializer(settings_obj).data)

    def patch(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and IsTenantAdmin().has_permission(request, self)):
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=request.tenant)
        serializer = TenantSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CurrentTenantFeatureFlagView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request, *args, **kwargs):
        flags = TenantFeatureFlag.objects.filter(tenant=request.tenant).order_by("key")
        return Response(TenantFeatureFlagSerializer(flags, many=True).data)

    def post(self, request, *args, **kwargs):
        if not (request.user.is_authenticated and IsTenantAdmin().has_permission(request, self)):
            return Response({"detail": "You do not have permission to perform this action."}, status=status.HTTP_403_FORBIDDEN)
        serializer = TenantFeatureFlagWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        flag, _ = TenantFeatureFlag.objects.update_or_create(
            tenant=request.tenant,
            key=serializer.validated_data["key"],
            defaults={
                "enabled": serializer.validated_data["enabled"],
                "description": serializer.validated_data.get("description", ""),
            },
        )
        return Response(TenantFeatureFlagSerializer(flag).data, status=status.HTTP_201_CREATED)


class CurrentTenantMembershipListCreateView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        memberships = (
            TenantMembership.objects.select_related("tenant", "user")
            .filter(tenant=tenant)
            .order_by("user__email")
        )
        return Response(TenantMembershipSerializer(memberships, many=True).data)

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        tenant = request.tenant
        actor_role = get_user_tenant_role(request.user, tenant)
        serializer = TenantMembershipWriteSerializer(
            data=request.data,
            context={"request": request, "actor_role": actor_role},
        )
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = None
        if data.get("user_id"):
            user = User.objects.filter(pk=data["user_id"]).first()
            if not user:
                return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)
        else:
            email = User.objects.normalize_email(data["email"]).lower()  # type: ignore[attr-defined]
            user = User.objects.filter(email__iexact=email).first()
            if not user:
                user = User.objects.create_user(
                    email=email,
                    username=data.get("username") or email.split("@")[0],
                    password=data["password"],
                    first_name=data.get("first_name", ""),
                    last_name=data.get("last_name", ""),
                )

        if user == request.user and data["role"] != actor_role and not is_platform_admin(request.user):
            return Response({"detail": "You cannot change your own role here."}, status=status.HTTP_400_BAD_REQUEST)

        membership, created = TenantMembership.objects.update_or_create(
            tenant=tenant,
            user=user,
            defaults={
                "role": data["role"],
                "is_active": data.get("is_active", True),
            },
        )
        if data["role"] in {
            TenantMembership.Role.TENANT_OWNER,
            TenantMembership.Role.TENANT_ADMIN,
            TenantMembership.Role.MANAGER,
            TenantMembership.Role.STAFF,
        } and not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(TenantMembershipSerializer(membership).data, status=status_code)


class CurrentTenantMembershipDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]

    def patch(self, request, membership_id, *args, **kwargs):
        tenant = request.tenant
        actor_role = get_user_tenant_role(request.user, tenant)
        membership = TenantMembership.objects.select_related("user", "tenant").filter(pk=membership_id, tenant=tenant).first()
        if not membership:
            return Response({"detail": "Membership not found."}, status=status.HTTP_404_NOT_FOUND)
        if membership.user == request.user and not is_platform_admin(request.user):
            return Response({"detail": "You cannot update your own membership here."}, status=status.HTTP_400_BAD_REQUEST)
        if actor_role and ROLE_ORDER.get(membership.role, 0) >= ROLE_ORDER.get(actor_role, 0) and not is_platform_admin(request.user):
            return Response({"detail": "You cannot modify a membership at or above your own role."}, status=status.HTTP_403_FORBIDDEN)

        serializer = TenantMembershipUpdateSerializer(
            data=request.data,
            context={"request": request, "actor_role": actor_role},
        )
        serializer.is_valid(raise_exception=True)
        for field, value in serializer.validated_data.items():
            setattr(membership, field, value)
        membership.save(update_fields=list(serializer.validated_data.keys()) or None)
        return Response(TenantMembershipSerializer(membership).data)
