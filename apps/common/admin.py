from django.contrib import admin

from apps.tenants.admin_mixins import TenantScopedAdminMixin
from .models import AuditLog, NewsletterSubscriber, SupportMessage


@admin.register(SupportMessage)
class SupportMessageAdmin(TenantScopedAdminMixin):
    list_display = ["id", "tenant", "email", "subject", "status", "assigned_to", "created_at"]
    list_filter = ["tenant", "status", "created_at"]
    search_fields = ["email", "name", "subject", "message"]
    readonly_fields = ["tenant", "user", "name", "email", "subject", "message", "resolved_at", "created_at", "updated_at"]
    autocomplete_fields = ["tenant", "user", "assigned_to"]


@admin.register(AuditLog)
class AuditLogAdmin(TenantScopedAdminMixin):
    list_display = ["created_at", "tenant", "actor", "action", "summary"]
    list_filter = ["tenant", "action", "created_at"]
    search_fields = ["summary", "action", "target_type", "target_id"]
    readonly_fields = ["tenant", "actor", "action", "target_type", "target_id", "summary", "metadata", "created_at", "updated_at"]
    autocomplete_fields = ["tenant", "actor"]


@admin.register(NewsletterSubscriber)
class NewsletterSubscriberAdmin(TenantScopedAdminMixin):
    list_display = [
        "email",
        "tenant",
        "is_active",
        "is_confirmed",
        "confirmed_at",
        "created_at",
    ]
    list_filter = ["tenant", "is_active", "is_confirmed", "created_at", "confirmed_at"]
    search_fields = ["email"]
    readonly_fields = ["confirmation_token", "confirmed_at", "created_at"]
    autocomplete_fields = ["tenant"]