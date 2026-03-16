from decimal import Decimal

from django.contrib import admin

from .models import Order, OrderItem


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ["product", "variant"]
    readonly_fields = [
        "product_title",
        "variant_name",
        "variant_sku",
        "unit_price",
        "line_total",
        "created_at",
        "updated_at",
    ]
    fields = [
        "product",
        "variant",
        "product_title",
        "variant_name",
        "variant_sku",
        "quantity",
        "unit_price",
        "line_total",
        "created_at",
        "updated_at",
    ]

    def line_total(self, obj):
        return obj.line_total if obj else Decimal("0.00")


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = [
        "slug",
        "user",
        "status",
        "total_price",
        "total_items",
        "created_at",
    ]
    list_filter = ["status", "created_at", "updated_at"]
    search_fields = ["slug", "user__email", "user__username"]
    readonly_fields = ["total_price", "created_at", "updated_at"]
    prepopulated_fields = {"slug": ("user",)}
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    ordering = ["-created_at"]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = [
        "order",
        "product_title",
        "variant_name",
        "variant_sku",
        "quantity",
        "unit_price",
        "line_total",
        "created_at",
    ]
    list_filter = ["created_at", "updated_at"]
    search_fields = [
        "order__slug",
        "product_title",
        "variant_name",
        "variant_sku",
    ]
    autocomplete_fields = ["order", "product", "variant"]
    readonly_fields = [
        "product_title",
        "variant_name",
        "variant_sku",
        "line_total",
        "created_at",
        "updated_at",
    ]

    def line_total(self, obj):
        return obj.line_total if obj else Decimal("0.00")