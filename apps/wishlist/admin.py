from django.contrib import admin
from .models import Wishlist, WishlistItem


class WishlistItemInline(admin.TabularInline):
    model = WishlistItem
    extra = 0
    autocomplete_fields = ["product"]
    readonly_fields = ["created_at", "updated_at"]
    show_change_link = True


@admin.register(Wishlist)
class WishlistAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "total_items",
        "created_at",
        "updated_at",
    )
    search_fields = (
        "user__email",
        "user__username",
    )
    list_filter = (
        "created_at",
        "updated_at",
    )
    ordering = ("-created_at",)
    inlines = [WishlistItemInline]
    autocomplete_fields = ["user"]
    readonly_fields = (
        "created_at",
        "updated_at",
        "total_items",
    )


@admin.register(WishlistItem)
class WishlistItemAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "wishlist",
        "product",
        "user_email",
        "created_at",
    )
    search_fields = (
        "product__title",
        "wishlist__user__email",
    )
    list_filter = (
        "created_at",
    )
    autocomplete_fields = [
        "wishlist",
        "product",
    ]
    readonly_fields = (
        "created_at",
        "updated_at",
    )

    def user_email(self, obj):
        return obj.wishlist.user.email
    user_email.short_description = "User"