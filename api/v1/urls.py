from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from apps.addresses import views as address_views
from apps.cart import views as cart_views
from apps.orders import views as order_views
from apps.products import views as product_views
from apps.reviews import views as review_views
from apps.users import views as user_views
from apps.wishlist import views as wishlist_views
from apps.payments import views as payment_views
from apps.inventory import views as inventory_views
from apps.shipping import views as shipping_views
from apps.promotions import views as promotions_views
from apps.notifications import views as notification_views

router = DefaultRouter()

router.register("users", user_views.UserViewSet, basename="users")
router.register("products", product_views.ProductViewSet, basename="products")
router.register("categories", product_views.CategoryViewSet, basename="categories")
router.register("cart", cart_views.CartViewSet, basename="cart")
router.register("cart-items", cart_views.CartItemViewSet, basename="cart-items")
router.register("orders", order_views.OrderViewSet, basename="orders")
router.register("order-items", order_views.OrderItemViewSet, basename="order-items")
router.register("reviews", review_views.ReviewViewSet, basename="reviews")
router.register("ratings", review_views.ProductRatingViewSet, basename="ratings")
router.register("wishlist", wishlist_views.WishlistViewSet, basename="wishlist")
router.register("wishlist-items", wishlist_views.WishlistItemViewSet, basename="wishlist-items")
router.register("addresses", address_views.CustomerAddressViewSet, basename="addresses")
router.register("payments", payment_views.PaymentViewSet, basename="payments")
router.register("inventory", inventory_views.InventoryViewSet, basename="inventory")
router.register("inventory-movements", inventory_views.InventoryMovementViewSet, basename="inventory-movements")
router.register("shipping-methods", shipping_views.ShippingMethodViewSet, basename="shipping-methods")
router.register("shipments", shipping_views.ShipmentViewSet, basename="shipments")
router.register("coupons", promotions_views.CouponViewSet, basename="coupons")
router.register("notifications", notification_views.NotificationViewSet, basename="notifications")

urlpatterns = [
    # Auth
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("auth/", include("dj_rest_auth.urls")),
    path("auth/registration/", include("dj_rest_auth.registration.urls")),
    path("auth/", include("apps.users.urls")),

    # Resources
    path("", include(router.urls)),
]