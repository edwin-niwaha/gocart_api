from django.db import transaction

from .models import Wishlist, WishlistItem


def get_or_create_wishlist(*, user) -> Wishlist:
    wishlist, _ = Wishlist.objects.get_or_create(user=user)
    return wishlist


@transaction.atomic
def add_item_to_wishlist(*, user, product) -> WishlistItem:
    wishlist = get_or_create_wishlist(user=user)
    item, _ = WishlistItem.objects.get_or_create(
        wishlist=wishlist,
        product=product,
    )
    return item


@transaction.atomic
def remove_wishlist_item(*, item: WishlistItem) -> None:
    item.delete()