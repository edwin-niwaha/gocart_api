from django.contrib import admin
from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "order",
        "user",
        "provider",
        "status",
        "currency",
        "amount",
        "paid_at",
        "created_at",
    )

    list_filter = (
        "provider",
        "status",
        "currency",
        "created_at",
        "paid_at",
    )

    search_fields = (
        "reference",
        "transaction_id",
        "order__slug",
        "user__email",
        "user__username",
    )

    readonly_fields = (
        "reference",
        "created_at",
        "updated_at",
        "provider_response",
    )

    autocomplete_fields = (
        "user",
        "order",
    )

    ordering = ("-created_at",)

    fieldsets = (
        ("Payment Information", {
            "fields": (
                "reference",
                "user",
                "order",
                "provider",
                "status",
            )
        }),
        ("Amount Details", {
            "fields": (
                "currency",
                "amount",
            )
        }),
        ("Provider Details", {
            "fields": (
                "transaction_id",
                "checkout_url",
                "provider_response",
            )
        }),
        ("Payment Dates", {
            "fields": (
                "paid_at",
            )
        }),
        ("Timestamps", {
            "fields": (
                "created_at",
                "updated_at",
            )
        }),
    )

    actions = ["mark_paid", "mark_failed", "mark_refunded"]

    @admin.action(description="Mark selected payments as PAID")
    def mark_paid(self, request, queryset):
        queryset.update(status=Payment.Status.PAID)

    @admin.action(description="Mark selected payments as FAILED")
    def mark_failed(self, request, queryset):
        queryset.update(status=Payment.Status.FAILED)

    @admin.action(description="Mark selected payments as REFUNDED")
    def mark_refunded(self, request, queryset):
        queryset.update(status=Payment.Status.REFUNDED)