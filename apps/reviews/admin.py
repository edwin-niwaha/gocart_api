from django.contrib import admin

from .models import ProductRating, Review


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "product",
        "rating",
        "short_comment",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "rating",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__email",
        "user__username",
        "product__title",
        "product__slug",
        "comment",
    )
    autocomplete_fields = ("user", "product")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    list_select_related = ("user", "product")

    fieldsets = (
        ("Review Info", {"fields": ("user", "product", "rating", "comment")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )

    @admin.display(description="Comment")
    def short_comment(self, obj):
        if not obj.comment:
            return "-"
        return obj.comment[:50] + ("..." if len(obj.comment) > 50 else "")


@admin.register(ProductRating)
class ProductRatingAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "product",
        "average_rating",
        "total_reviews",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "product__title",
        "product__slug",
    )
    autocomplete_fields = ("product",)
    readonly_fields = (
        "average_rating",
        "total_reviews",
        "created_at",
        "updated_at",
    )
    ordering = ("-updated_at",)
    list_select_related = ("product",)

    fieldsets = (
        ("Rating Summary", {"fields": ("product", "average_rating", "total_reviews")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )