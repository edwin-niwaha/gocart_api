from apps.tenants.admin_mixins import TenantScopedAdminMixin
from django.contrib import admin
from .models import DeliveryRate, PickupStation, ShippingMethod


@admin.register(ShippingMethod)
class ShippingMethodAdmin(TenantScopedAdminMixin):
    list_display = (
        "name",
        "fee",
        "estimated_days",
        "is_active",
        "created_at",
    )

    list_filter = ("is_active", "estimated_days")

    search_fields = ("name", "description")

    ordering = ("name",)

    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "name",
                "description",
            )
        }),
        ("Shipping Details", {
            "fields": (
                "fee",
                "estimated_days",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )


@admin.register(PickupStation)
class PickupStationAdmin(TenantScopedAdminMixin):
    list_display = (
        "name",
        "tenant",
        "city",
        "area",
        "is_active",
        "created_at",
    )
    list_filter = ("tenant", "city", "is_active", "created_at")
    search_fields = ("name", "city", "area", "address", "phone")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("tenant",)
    fieldsets = (
        ("Station Details", {
            "fields": (
                "tenant",
                "name",
                "city",
                "area",
                "address",
                "phone",
                "opening_hours",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )


@admin.register(DeliveryRate)
class DeliveryRateAdmin(TenantScopedAdminMixin):
    list_display = (
        "tenant",
        "region",
        "city",
        "area",
        "fee",
        "estimated_days",
        "is_active",
        "created_at",
    )
    list_filter = ("tenant", "region", "is_active", "estimated_days")
    search_fields = ("city", "area")
    readonly_fields = ("created_at", "updated_at")
    autocomplete_fields = ("tenant",)
    fieldsets = (
        ("Coverage", {
            "fields": (
                "tenant",
                "region",
                "city",
                "area",
            )
        }),
        ("Pricing", {
            "fields": (
                "fee",
                "estimated_days",
                "is_active",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )
