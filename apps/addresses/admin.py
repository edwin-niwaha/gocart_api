from django.contrib import admin
from .models import CustomerAddress


@admin.register(CustomerAddress)
class CustomerAddressAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "label",
        "city",
        "country",
        "phone_number",
        "is_default",
        "created_at",
    )
    list_filter = (
        "is_default",
        "country",
        "city",
        "created_at",
    )
    search_fields = (
        "user__email",
        "label",
        "city",
        "country",
        "postal_code",
        "phone_number",
    )
    ordering = ("-is_default", "-created_at")
    autocomplete_fields = ("user",)

    fieldsets = (
        ("User Information", {
            "fields": ("user", "label")
        }),
        ("Address Details", {
            "fields": (
                "address_line1",
                "address_line2",
                "city",
                "state",
                "postal_code",
                "country",
            )
        }),
        ("Contact", {
            "fields": ("phone_number",)
        }),
        ("Settings", {
            "fields": ("is_default",)
        }),
        ("Timestamps", {
            "fields": ("created_at", "updated_at"),
        }),
    )

    readonly_fields = ("created_at", "updated_at")