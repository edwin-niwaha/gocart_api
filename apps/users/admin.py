from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    model = CustomUser

    list_display = (
        "email",
        "username",
        "user_type",
        "avatar_preview",
        "is_staff",
        "active_tenant_display",
        "created_at",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
        "avatar_preview",
    )

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "avatar",
                    "avatar_preview",
                )
            },
        ),
        (
            "Permissions",
            {
                "fields": (
                    "user_type",
                    "is_active",
                    "is_staff",
                    "is_superuser",
                    "groups",
                    "user_permissions",
                )
            },
        ),
        (
            "Dates",
            {"fields": ("last_login", "created_at", "updated_at")},
        ),
    )

    # ✅ FIXED preview
    def avatar_preview(self, obj):
        if obj.avatar:
            try:
                return format_html(
                    '<img src="{}" width="50" height="50" style="border-radius:50%; object-fit:cover;" />',
                    obj.avatar.url,
                )
            except Exception:
                return "Invalid image"
        return "No Image"

    avatar_preview.short_description = "Avatar"
    def active_tenant_display(self, obj):
        tenant = obj.active_tenant
        return tenant.slug if tenant else "—"

    active_tenant_display.short_description = "Active tenant"
