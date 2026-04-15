from apps.tenants.admin_mixins import TenantScopedAdminMixin
from django.contrib import admin
from .models import ShippingMethod, Shipment


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


@admin.register(Shipment)
class ShipmentAdmin(TenantScopedAdminMixin):
    list_display = (
        "order",
        "shipping_method",
        "status",
        "tracking_number",
        "shipping_fee",
        "dispatched_at",
        "delivered_at",
        "created_at",
    )

    list_filter = (
        "status",
        "shipping_method",
        "created_at",
        "dispatched_at",
        "delivered_at",
    )

    search_fields = (
        "order__slug",
        "tracking_number",
        "address__city",
        "address__country",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    autocomplete_fields = (
        "order",
        "address",
        "shipping_method",
    )

    fieldsets = (
        ("Order Information", {
            "fields": (
                "order",
                "address",
                "shipping_method",
            )
        }),
        ("Shipment Details", {
            "fields": (
                "status",
                "tracking_number",
                "shipping_fee",
            )
        }),
        ("Tracking Dates", {
            "fields": (
                "dispatched_at",
                "delivered_at",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )