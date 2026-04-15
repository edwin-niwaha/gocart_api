from apps.tenants.admin_mixins import TenantScopedAdminMixin
from django.contrib import admin
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(TenantScopedAdminMixin):
    list_display = (
        "user",
        "notification_type",
        "title",
        "is_read",
        "created_at",
        "read_at",
    )

    list_filter = (
        "notification_type",
        "is_read",
        "created_at",
    )

    search_fields = (
        "user__email",
        "title",
        "message",
    )

    ordering = ("-created_at",)

    autocomplete_fields = ("user",)

    readonly_fields = (
        "created_at",
        "updated_at",
        "read_at",
    )

    fieldsets = (
        ("User", {
            "fields": ("user",)
        }),

        ("Notification Content", {
            "fields": (
                "notification_type",
                "title",
                "message",
                "data",
            )
        }),

        ("Status", {
            "fields": (
                "is_read",
                "read_at",
            )
        }),

        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )