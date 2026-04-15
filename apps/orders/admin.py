from apps.tenants.admin_mixins import TenantScopedAdminMixin
from decimal import Decimal

from django.contrib import admin

from .models import Order, OrderItem, OrderStatusEvent


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    autocomplete_fields = ["tenant", "product", "variant"]
    readonly_fields = [
        "tenant",
        "product_title",
        "variant_name",
        "variant_sku",
        "unit_price",
        "line_total",
        "created_at",
        "updated_at",
    ]
    fields = [
        "tenant",
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
class OrderAdmin(TenantScopedAdminMixin):
    list_display = [
        "slug",
        "tenant",
        "user",
        "status",
        "total_price",
        "total_items",
        "created_at",
    ]
    list_filter = ["tenant", "status", "created_at", "updated_at"]
    search_fields = ["slug", "tenant__name", "user__email", "user__username"]
    readonly_fields = ["total_price", "created_at", "updated_at"]
    inlines = [OrderItemInline]
    date_hierarchy = "created_at"
    ordering = ["tenant", "-created_at"]
    autocomplete_fields = ["tenant", "user", "address"]


@admin.register(OrderItem)
class OrderItemAdmin(TenantScopedAdminMixin):
    list_display = [
        "order",
        "tenant",
        "product_title",
        "variant_name",
        "variant_sku",
        "quantity",
        "unit_price",
        "line_total",
        "created_at",
    ]
    list_filter = ["tenant", "created_at", "updated_at"]
    search_fields = [
        "order__slug",
        "tenant__name",
        "product_title",
        "variant_name",
        "variant_sku",
    ]
    autocomplete_fields = ["tenant", "order", "product", "variant"]
    readonly_fields = [
        "tenant",
        "product_title",
        "variant_name",
        "variant_sku",
        "line_total",
        "created_at",
        "updated_at",
    ]

    def line_total(self, obj):
        return obj.line_total if obj else Decimal("0.00")


@admin.register(OrderStatusEvent)
class OrderStatusEventAdmin(TenantScopedAdminMixin):
    list_display = ["order", "tenant", "from_status", "to_status", "changed_by", "created_at"]
    list_filter = ["tenant", "from_status", "to_status", "created_at"]
    search_fields = ["order__slug", "note", "changed_by__email"]
    autocomplete_fields = ["tenant", "order", "changed_by"]
    readonly_fields = ["tenant", "order", "changed_by", "from_status", "to_status", "note", "created_at", "updated_at"]
