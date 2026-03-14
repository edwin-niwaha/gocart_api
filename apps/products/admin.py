from django.contrib import admin
from .models import Category, Product, ProductVariant


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = (
        "name",
        "sku",
        "price",
        "stock_quantity",
        "max_quantity_per_order",
        "is_active",
        "sort_order",
    )


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "is_active", "created_at")
    list_filter = ("is_active", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    ordering = ("name",)


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
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
        "category",
        "base_price_display",
        "variant_count",
        "featured_badge",
        "is_active",
        "created_at",
    )

    list_filter = (
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
        "variants__name",
        "variants__sku",
    )

    prepopulated_fields = {"slug": ("title",)}
    autocomplete_fields = ("category",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "title",
                "slug",
                "category",
                "description",
            )
        }),
        ("Images", {
            "fields": (
                "hero_image",
                "image_urls",
            )
        }),
        ("Status", {
            "fields": (
                "is_active",
                "is_featured",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    ordering = ("-created_at",)


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "name",
        "sku",
        "price",
        "stock_quantity",
        "is_active",
        "sort_order",
        "created_at",
    )
    list_filter = ("is_active", "product__category", "created_at")
    search_fields = ("product__title", "name", "sku")
    autocomplete_fields = ("product",)
    ordering = ("product", "sort_order", "price")