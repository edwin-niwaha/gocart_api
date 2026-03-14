from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ["variant"]
    readonly_fields = ("unit_price", "line_total", "created_at", "updated_at")
    fields = (
        "variant",
        "quantity",
        "unit_price",
        "line_total",
        "created_at",
        "updated_at",
    )

    def has_change_permission(self, request, obj=None):
        return True


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "total_items",
        "total_price",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__email",
        "user__username",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "total_items",
        "total_price",
    )
    inlines = [CartItemInline]


@admin.register(CartItem)
class CartItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "cart",
        "product_title",
        "variant",
        "quantity",
        "unit_price",
        "line_total",
        "is_available",
        "created_at",
    )
    list_filter = (
        "variant__is_active",
        "variant__product__is_active",
        "created_at",
    )
    search_fields = (
        "cart__user__email",
        "cart__user__username",
        "variant__product__title",
        "variant__name",
        "variant__sku",
    )
    autocomplete_fields = ("cart", "variant")
    readonly_fields = (
        "unit_price",
        "line_total",
        "is_available",
        "created_at",
        "updated_at",
    )

    def product_title(self, obj):
        return obj.variant.product.title

    product_title.short_description = "Product"