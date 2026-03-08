from rest_framework.routers import DefaultRouter

from .views import CouponViewSet

router = DefaultRouter()
router.register("coupons", CouponViewSet, basename="coupons")

urlpatterns = router.urls