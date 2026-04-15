from __future__ import annotations

from django.contrib import admin

from .models import TenantMembership
from .permissions import ROLE_ORDER, get_user_tenant_role, is_platform_admin


class TenantScopedAdminMixin(admin.ModelAdmin):
    tenant_field_name = "tenant"
    view_role = TenantMembership.Role.STAFF
    change_role = TenantMembership.Role.MANAGER
    delete_role = TenantMembership.Role.TENANT_ADMIN

    def get_user_tenants(self, request):
        return request.user.tenant_memberships.filter(is_active=True, tenant__is_active=True).values_list("tenant_id", flat=True)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if is_platform_admin(request.user):
            return queryset
        field = f"{self.tenant_field_name}_id"
        return queryset.filter(**{f"{field}__in": self.get_user_tenants(request)})

    def _has_role(self, request, minimum_role):
        if is_platform_admin(request.user):
            return True
        tenant_ids = set(self.get_user_tenants(request))
        if not tenant_ids:
            return False
        memberships = request.user.tenant_memberships.filter(tenant_id__in=tenant_ids, is_active=True).values_list("role", flat=True)
        return any(ROLE_ORDER.get(role, 0) >= ROLE_ORDER.get(minimum_role, 0) for role in memberships)

    def has_module_permission(self, request):
        return request.user.is_authenticated and self._has_role(request, self.view_role)

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return request.user.is_authenticated and self._has_role(request, self.change_role)

    def has_change_permission(self, request, obj=None):
        return request.user.is_authenticated and self._has_role(request, self.change_role)

    def has_delete_permission(self, request, obj=None):
        return request.user.is_authenticated and self._has_role(request, self.delete_role)
