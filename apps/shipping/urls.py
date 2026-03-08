from rest_framework.routers import DefaultRouter

from .views import ShipmentViewSet, ShippingMethodViewSet

router = DefaultRouter()
router.register("shipping-methods", ShippingMethodViewSet, basename="shipping-methods")
router.register("shipments", ShipmentViewSet, basename="shipments")

urlpatterns = router.urls