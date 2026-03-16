from django.contrib import admin
from .models import Coupon


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "discount_type",
        "value",
        "min_order_amount",
        "usage_limit",
        "used_count",
        "starts_at",
        "ends_at",
        "is_active",
        "is_valid_now",
        "created_at",
    )

    list_filter = (
        "discount_type",
        "is_active",
        "starts_at",
        "ends_at",
        "created_at",
    )

    search_fields = ("code", "description")

    readonly_fields = (
        "used_count",
        "created_at",
        "updated_at",
        "is_valid_now",
    )

    filter_horizontal = (
        "products",
        "categories",
    )

    fieldsets = (
        ("Basic Information", {
            "fields": (
                "code",
                "description",
                "discount_type",
                "value",
                "is_active",
            )
        }),
        ("Conditions", {
            "fields": (
                "min_order_amount",
                "max_discount_amount",
                "usage_limit",
                "used_count",
            )
        }),
        ("Validity Period", {
            "fields": (
                "starts_at",
                "ends_at",
                "is_valid_now",
            )
        }),
        ("Applicability", {
            "fields": (
                "products",
                "categories",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )