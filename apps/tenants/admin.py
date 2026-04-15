from django.contrib import admin

from .models import Tenant, TenantBranding, TenantFeatureFlag, TenantMembership, TenantSettings


class TenantBrandingInline(admin.StackedInline):
    model = TenantBranding
    extra = 0


class TenantSettingsInline(admin.StackedInline):
    model = TenantSettings
    extra = 0


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "is_default", "currency", "support_email")
    list_filter = ("is_active", "is_default", "currency")
    search_fields = ("name", "slug", "support_email")
    inlines = [TenantBrandingInline, TenantSettingsInline]


@admin.register(TenantMembership)
class TenantMembershipAdmin(admin.ModelAdmin):
    list_display = ("tenant", "user", "role", "is_active", "created_at")
    list_filter = ("tenant", "role", "is_active")
    search_fields = ("tenant__name", "tenant__slug", "user__email", "user__username")


@admin.register(TenantFeatureFlag)
class TenantFeatureFlagAdmin(admin.ModelAdmin):
    list_display = ("tenant", "key", "enabled", "description", "updated_at")
    list_filter = ("tenant", "enabled")
    search_fields = ("tenant__slug", "key", "description")
