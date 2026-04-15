from apps.tenants.admin_mixins import TenantScopedAdminMixin
from django.contrib import admin
from .models import Category, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = (
        "tenant",
        "name",
        "sku",
        "price",
        "stock_quantity",
        "max_quantity_per_order",
        "is_active",
        "sort_order",
    )
    readonly_fields = ("tenant",)


@admin.register(Category)
class CategoryAdmin(TenantScopedAdminMixin):
    list_display = ("name", "tenant", "slug", "is_active", "created_at")
    list_filter = ("tenant", "is_active", "created_at")
    search_fields = ("name", "slug", "tenant__name", "tenant__slug")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("tenant",)
    ordering = ("tenant", "name")


@admin.register(Product)
class ProductAdmin(TenantScopedAdminMixin):
    inlines = [ProductVariantInline]

    def featured_badge(self, obj):
        return "⭐ Featured" if obj.is_featured else "—"

    featured_badge.short_description = "Featured"
    featured_badge.admin_order_field = "is_featured"

    def variant_count(self, obj):
        return obj.variants.count()

    variant_count.short_description = "Variants"

    def base_price_display(self, obj):
        return obj.base_price

    base_price_display.short_description = "Base price"

    list_display = (
        "title",
        "tenant",
        "category",
        "base_price_display",
        "variant_count",
        "featured_badge",
        "is_active",
        "created_at",
    )

    list_filter = (
        "tenant",
        "category",
        "is_active",
        "is_featured",
        "created_at",
    )

    list_editable = ("is_active",)

    search_fields = (
        "title",
        "slug",
        "description",
        "tenant__name",
        "variants__name",
        "variants__sku",
    )

    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("tenant", "category")
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Information", {"fields": ("tenant", "title", "slug", "category", "description")}),
        ("Images", {"fields": ("hero_image", "image_urls")}),
        ("Status", {"fields": ("is_active", "is_featured")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    ordering = ("tenant", "-created_at")


@admin.register(ProductVariant)
class ProductVariantAdmin(TenantScopedAdminMixin):
    list_display = (
        "product",
        "tenant",
        "name",
        "sku",
        "price",
        "stock_quantity",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = ("tenant", "is_active", "product__category", "created_at")
    search_fields = ("product__title", "tenant__name", "name", "sku")
    autocomplete_fields = ("tenant", "product")
    ordering = ("tenant", "product", "sort_order", "price")
