from rest_framework.routers import DefaultRouter

from .views import CartItemViewSet, CartViewSet

router = DefaultRouter()
router.register("carts", CartViewSet, basename="carts")
router.register("cart-items", CartItemViewSet, basename="cart-items")

urlpatterns = router.urls