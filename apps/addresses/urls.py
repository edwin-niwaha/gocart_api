from rest_framework.routers import DefaultRouter

from .views import CustomerAddressViewSet

router = DefaultRouter()
router.register("addresses", CustomerAddressViewSet, basename="addresses")

urlpatterns = router.urls