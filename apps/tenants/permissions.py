from __future__ import annotations

from typing import Iterable

from rest_framework import permissions

from .models import Tenant, TenantMembership

ROLE_ORDER = {
    TenantMembership.Role.STAFF: 10,
    TenantMembership.Role.MANAGER: 20,
    TenantMembership.Role.TENANT_ADMIN: 30,
    TenantMembership.Role.TENANT_OWNER: 40,
    TenantMembership.Role.SUPER_ADMIN: 100,
}


def is_platform_admin(user) -> bool:
    return bool(
        getattr(user, "is_authenticated", False)
        and (getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "ADMIN")
    )


def get_user_tenant_membership(user, tenant: Tenant | None) -> TenantMembership | None:
    if tenant is None or not getattr(user, "is_authenticated", False):
        return None
    return (
        user.tenant_memberships.select_related("tenant")
        .filter(tenant=tenant, is_active=True, tenant__is_active=True)
        .order_by("created_at")
        .first()
    )


def get_user_tenant_role(user, tenant: Tenant | None) -> str | None:
    if is_platform_admin(user):
        return TenantMembership.Role.SUPER_ADMIN
    membership = get_user_tenant_membership(user, tenant)
    return membership.role if membership else None


def user_has_tenant_role(user, tenant: Tenant | None, minimum_role: str) -> bool:
    role = get_user_tenant_role(user, tenant)
    if not role:
        return False
    return ROLE_ORDER.get(role, -1) >= ROLE_ORDER.get(minimum_role, 9999)


def user_has_any_tenant_role(user, tenant: Tenant | None, allowed_roles: Iterable[str]) -> bool:
    role = get_user_tenant_role(user, tenant)
    return role in set(allowed_roles)


class IsTenantRole(permissions.BasePermission):
    minimum_role = TenantMembership.Role.STAFF

    def has_permission(self, request, view):
        tenant = getattr(request, "tenant", None)
        return user_has_tenant_role(request.user, tenant, self.minimum_role)


class IsTenantStaff(IsTenantRole):
    minimum_role = TenantMembership.Role.STAFF


class IsTenantManager(IsTenantRole):
    minimum_role = TenantMembership.Role.MANAGER


class IsTenantAdmin(IsTenantRole):
    minimum_role = TenantMembership.Role.TENANT_ADMIN


class IsTenantOwner(IsTenantRole):
    minimum_role = TenantMembership.Role.TENANT_OWNER


class IsTenantAdminOrReadOnly(permissions.BasePermission):
    minimum_role = TenantMembership.Role.TENANT_ADMIN

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return user_has_tenant_role(request.user, getattr(request, "tenant", None), self.minimum_role)
