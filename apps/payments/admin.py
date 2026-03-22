from django.contrib import admin

from .models import Payment


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = (
        "reference",
        "user",
        "order",
        "provider",
        "status",
        "amount",
        "currency",
        "phone_number",
        "created_at",
        "paid_at",
    )
    list_filter = ("provider", "status", "currency", "created_at", "paid_at")
    search_fields = (
        "reference",
        "transaction_id",
        "external_id",
        "phone_number",
        "order__slug",
        "user__email",
        "user__username",
    )
    readonly_fields = (
        "reference",
        "transaction_id",
        "external_id",
        "provider_response",
        "created_at",
        "updated_at",
        "paid_at",
    )