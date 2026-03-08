from django.contrib import admin

from .models import CustomUser


@admin.register(CustomUser)
class CustomUserAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "email",
        "username",
        "user_type",
        "is_active",
        "is_staff",
        "created_at",
    )
    search_fields = ("email", "username", "first_name", "last_name")
    list_filter = ("user_type", "is_active", "is_staff", "is_superuser")
    ordering = ("-created_at",)
    readonly_fields = ("created_at", "updated_at")