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
        "profile_image_preview",
        "is_staff",
        "created_at",
    )

    readonly_fields = ("created_at", "updated_at", "profile_image_preview")

    fieldsets = (
        (None, {"fields": ("email", "username", "password")}),
        (
            "Profile",
            {
                "fields": (
                    "profile_picture_url",
                    "profile_image_preview",
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

    def profile_image_preview(self, obj):
        if obj.profile_picture_url:
            return format_html(
                '<img src="{}" width="40" height="40" style="border-radius:50%;" />',
                obj.profile_picture_url,
            )
        return "No Image"

    profile_image_preview.short_description = "Profile"