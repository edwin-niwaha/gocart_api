from django.contrib.auth import get_user_model
from django.db.models import Q
from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError
from rest_framework.generics import GenericAPIView
from rest_framework.pagination import PageNumberPagination
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

STAFF_ROLES = {
    TenantMembership.Role.SUPER_ADMIN,
    TenantMembership.Role.TENANT_OWNER,
    TenantMembership.Role.TENANT_ADMIN,
    TenantMembership.Role.MANAGER,
    TenantMembership.Role.STAFF,
}


class MembershipPagination(PageNumberPagination):
    page_size_query_param = "page_size"
    max_page_size = 100


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
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantAdmin()]

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        branding, _ = TenantBranding.objects.get_or_create(tenant=tenant, defaults={"app_name": tenant.name})
        return Response(TenantBrandingSerializer(branding).data)

    def patch(self, request, *args, **kwargs):
        branding, _ = TenantBranding.objects.get_or_create(tenant=request.tenant, defaults={"app_name": request.tenant.name})
        serializer = TenantBrandingSerializer(branding, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CurrentTenantSettingsView(APIView):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantAdmin()]

    def get(self, request, *args, **kwargs):
        tenant = request.tenant
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=tenant)
        return Response(TenantSettingsSerializer(settings_obj).data)

    def patch(self, request, *args, **kwargs):
        settings_obj, _ = TenantSettings.objects.get_or_create(tenant=request.tenant)
        serializer = TenantSettingsSerializer(settings_obj, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class CurrentTenantFeatureFlagView(APIView):
    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantAdmin()]

    def get(self, request, *args, **kwargs):
        flags = TenantFeatureFlag.objects.filter(tenant=request.tenant).order_by("key")
        return Response(TenantFeatureFlagSerializer(flags, many=True).data)

    def post(self, request, *args, **kwargs):
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


def sync_user_staff_status(user) -> None:
    if is_platform_admin(user):
        if not user.is_staff:
            user.is_staff = True
            user.save(update_fields=["is_staff"])
        return

    has_active_staff_role = user.tenant_memberships.filter(
        is_active=True,
        role__in=STAFF_ROLES,
        tenant__is_active=True,
    ).exists()

    if user.is_staff != has_active_staff_role:
        user.is_staff = has_active_staff_role
        user.save(update_fields=["is_staff"])


def apply_membership_search(queryset, search_term: str):
    if not search_term:
        return queryset

    query = search_term.strip()
    if not query:
        return queryset

    return queryset.filter(
        Q(user__email__icontains=query)
        | Q(user__username__icontains=query)
        | Q(user__first_name__icontains=query)
        | Q(user__last_name__icontains=query)
        | Q(role__icontains=query)
    )


def apply_membership_status_filter(queryset, raw_status: str):
    if not raw_status:
        return queryset

    normalized = raw_status.strip().lower()
    if normalized in {"active", "true", "1"}:
        return queryset.filter(is_active=True, user__is_active=True)
    if normalized in {"inactive", "false", "0"}:
        return queryset.filter(Q(is_active=False) | Q(user__is_active=False))
    return queryset


class CurrentTenantMembershipListCreateView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    serializer_class = TenantMembershipSerializer
    pagination_class = MembershipPagination

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = (
            TenantMembership.objects.select_related("tenant", "user")
            .filter(tenant=tenant)
            .order_by("user__email", "id")
        )
        queryset = apply_membership_search(
            queryset,
            self.request.query_params.get("search", ""),
        )

        status_value = (
            self.request.query_params.get("status")
            or self.request.query_params.get("is_active")
            or ""
        )
        return apply_membership_status_filter(queryset, status_value)

    def get(self, request, *args, **kwargs):
        memberships = self.get_queryset()

        if "page" in request.query_params or "page_size" in request.query_params:
            page = self.paginate_queryset(memberships)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(memberships, many=True)
        return Response(serializer.data)

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
                raise NotFound("User not found.")
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
            raise ValidationError({"detail": "You cannot change your own role here."})

        membership, created = TenantMembership.objects.update_or_create(
            tenant=tenant,
            user=user,
            defaults={
                "role": data["role"],
                "is_active": data.get("is_active", True),
            },
        )
        sync_user_staff_status(user)

        status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
        return Response(TenantMembershipSerializer(membership).data, status=status_code)


class CurrentTenantMembershipDetailView(GenericAPIView):
    permission_classes = [permissions.IsAuthenticated, IsTenantAdmin]
    serializer_class = TenantMembershipSerializer

    def get_object(self):
        membership = (
            TenantMembership.objects.select_related("user", "tenant")
            .filter(pk=self.kwargs["membership_id"], tenant=self.request.tenant)
            .first()
        )
        if not membership:
            raise NotFound("Membership not found.")
        return membership

    def _validate_manageable_membership(self, membership):
        actor_role = get_user_tenant_role(self.request.user, self.request.tenant)
        if membership.user == self.request.user and not is_platform_admin(self.request.user):
            raise ValidationError({"detail": "You cannot update your own membership here."})
        if (
            actor_role
            and ROLE_ORDER.get(membership.role, 0) >= ROLE_ORDER.get(actor_role, 0)
            and not is_platform_admin(self.request.user)
        ):
            raise PermissionDenied("You cannot modify a membership at or above your own role.")
        return actor_role

    def get(self, request, membership_id, *args, **kwargs):
        membership = self.get_object()
        self._validate_manageable_membership(membership)
        return Response(self.get_serializer(membership).data)

    def patch(self, request, membership_id, *args, **kwargs):
        membership = self.get_object()
        actor_role = self._validate_manageable_membership(membership)

        serializer = TenantMembershipUpdateSerializer(
            data=request.data,
            context={
                "request": request,
                "actor_role": actor_role,
                "membership": membership,
            },
        )
        serializer.is_valid(raise_exception=True)

        membership_fields = []
        for field in ("role", "is_active"):
            if field in serializer.validated_data:
                setattr(membership, field, serializer.validated_data[field])
                membership_fields.append(field)

        if membership_fields:
            membership.save(update_fields=membership_fields + ["updated_at"])

        user = membership.user
        user_fields = []
        user_field_map = {
            "email": "email",
            "username": "username",
            "first_name": "first_name",
            "last_name": "last_name",
            "user_is_active": "is_active",
        }
        for incoming_field, user_field in user_field_map.items():
            if incoming_field in serializer.validated_data:
                setattr(user, user_field, serializer.validated_data[incoming_field])
                user_fields.append(user_field)

        if "password" in serializer.validated_data:
            user.set_password(serializer.validated_data["password"])
            user_fields.append("password")

        if user_fields:
            user.save(update_fields=list(dict.fromkeys(user_fields)))

        sync_user_staff_status(user)
        membership.refresh_from_db()
        return Response(self.get_serializer(membership).data)

    @transaction.atomic
    def delete(self, request, membership_id, *args, **kwargs):
        membership = self.get_object()
        self._validate_manageable_membership(membership)

        user = membership.user
        membership.delete()
        sync_user_staff_status(user)
        return Response(status=status.HTTP_204_NO_CONTENT)
