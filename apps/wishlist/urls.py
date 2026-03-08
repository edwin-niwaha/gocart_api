from rest_framework.routers import DefaultRouter

from .views import WishlistItemViewSet, WishlistViewSet

router = DefaultRouter()
router.register("wishlists", WishlistViewSet, basename="wishlists")
router.register("wishlist-items", WishlistItemViewSet, basename="wishlist-items")

urlpatterns = router.urls