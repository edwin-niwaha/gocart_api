from django.db import transaction

from .models import Tenant, TenantBranding, TenantSettings


@transaction.atomic
def ensure_default_tenant() -> Tenant:
    tenant = Tenant.objects.filter(is_default=True).first()
    if tenant:
        return tenant

    tenant, _ = Tenant.objects.get_or_create(
        slug="default",
        defaults={
            "name": "GoCart Default",
            "is_active": True,
            "is_default": True,
        },
    )

    if not tenant.is_default:
        tenant.is_default = True
        tenant.is_active = True
        tenant.save(update_fields=["is_default", "is_active", "updated_at"])

    TenantBranding.objects.get_or_create(tenant=tenant, defaults={"app_name": tenant.name})
    TenantSettings.objects.get_or_create(tenant=tenant)
    return tenant


def get_default_tenant() -> Tenant:
    tenant = Tenant.objects.filter(is_default=True, is_active=True).first()
    if tenant:
        return tenant
    return ensure_default_tenant()
