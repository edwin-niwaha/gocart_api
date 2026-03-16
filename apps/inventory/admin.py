from django.contrib import admin
from .models import Inventory, InventoryMovement


class InventoryMovementInline(admin.TabularInline):
    model = InventoryMovement
    extra = 0
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)


@admin.register(Inventory)
class InventoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "stock_quantity",
        "reserved_quantity",
        "available_quantity",
        "low_stock_threshold",
        "is_in_stock",
        "created_at",
    )

    list_filter = (
        "is_in_stock",
        "created_at",
    )

    search_fields = (
        "product__title",
    )

    readonly_fields = (
        "available_quantity",
        "created_at",
        "updated_at",
    )

    ordering = ("product__title",)

    autocomplete_fields = ("product",)

    fieldsets = (
        ("Product", {
            "fields": ("product",)
        }),
        ("Stock Information", {
            "fields": (
                "stock_quantity",
                "reserved_quantity",
                "available_quantity",
                "low_stock_threshold",
                "is_in_stock",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )

    inlines = [InventoryMovementInline]


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = (
        "inventory",
        "movement_type",
        "quantity",
        "note",
        "created_at",
    )

    list_filter = (
        "movement_type",
        "created_at",
    )

    search_fields = (
        "inventory__product__title",
        "note",
    )

    ordering = ("-created_at",)

    autocomplete_fields = ("inventory",)

    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Movement Details", {
            "fields": (
                "inventory",
                "movement_type",
                "quantity",
                "note",
            )
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )