from __future__ import annotations

from typing import Optional

from .models import Tenant, TenantMembership
from .permissions import get_user_tenant_role, is_platform_admin, user_has_tenant_role
from .services import get_default_tenant

TENANT_HEADER = "HTTP_X_TENANT_SLUG"
TENANT_QUERY_PARAM = "tenant"


class TenantResolutionError(Exception):
    pass


def resolve_tenant_from_request(request) -> Tenant:
    query_params = getattr(request, "query_params", None)
    headers = getattr(request, "headers", {})
    slug = (
        request.META.get(TENANT_HEADER)
        or headers.get("X-Tenant-Slug")
        or (query_params.get(TENANT_QUERY_PARAM) if query_params is not None else None)
        or request.GET.get(TENANT_QUERY_PARAM)
        or ""
    ).strip().lower()

    if slug:
        tenant = Tenant.objects.filter(slug__iexact=slug, is_active=True).first()
        if tenant:
            return tenant
        raise TenantResolutionError("Tenant not found.")

    if request.user.is_authenticated:
        membership = (
            request.user.tenant_memberships.select_related("tenant")
            .filter(is_active=True, tenant__is_active=True)
            .order_by("created_at")
            .first()
        )
        if membership:
            return membership.tenant

    return get_default_tenant()


def user_has_tenant_access(user, tenant: Optional[Tenant]) -> bool:
    if tenant is None:
        return False
    if is_platform_admin(user):
        return True
    if not getattr(user, "is_authenticated", False):
        return False
    return user.tenant_memberships.filter(tenant=tenant, is_active=True).exists()


def user_is_tenant_staff(user, tenant: Optional[Tenant]) -> bool:
    return user_has_tenant_role(user, tenant, TenantMembership.Role.STAFF)


def user_is_tenant_manager(user, tenant: Optional[Tenant]) -> bool:
    return user_has_tenant_role(user, tenant, TenantMembership.Role.MANAGER)


def user_is_tenant_admin(user, tenant: Optional[Tenant]) -> bool:
    return user_has_tenant_role(user, tenant, TenantMembership.Role.TENANT_ADMIN)


def user_is_tenant_owner(user, tenant: Optional[Tenant]) -> bool:
    return user_has_tenant_role(user, tenant, TenantMembership.Role.TENANT_OWNER)


def get_request_tenant_role(request) -> str | None:
    return get_user_tenant_role(request.user, getattr(request, "tenant", None))
