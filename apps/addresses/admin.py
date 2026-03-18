from django.contrib import admin

from .models import CustomerAddress


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "city",
        "region",
        "phone_number",
        "is_default",
        "created_at",
        "updated_at",
    )
    list_filter = (
        "region",
        "is_default",
        "city",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__email",
        "user__username",
        "street_name",
        "city",
        "phone_number",
        "additional_telephone",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
    )
    ordering = ("-is_default", "-created_at")
    autocomplete_fields = ("user",)

    fieldsets = (
        ("User", {
            "fields": ("user",)
        }),
        ("Address Details", {
            "fields": (
                "street_name",
                "city",
                "region",
                "additional_information",
            )
        }),
        ("Contact Details", {
            "fields": (
                "phone_number",
                "additional_telephone",
            )
        }),
        ("Settings", {
            "fields": ("is_default",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at")
        }),
    )