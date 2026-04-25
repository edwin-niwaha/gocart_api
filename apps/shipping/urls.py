from rest_framework.routers import DefaultRouter

from .views import (
    DeliveryRateViewSet,
    PickupStationViewSet,
    ShipmentViewSet,
    ShippingMethodViewSet,
)

router = DefaultRouter()
router.register("shipping-methods", ShippingMethodViewSet, basename="shipping-methods")
router.register("pickup-stations", PickupStationViewSet, basename="pickup-stations")
router.register("delivery-rates", DeliveryRateViewSet, basename="delivery-rates")
router.register("shipments", ShipmentViewSet, basename="shipments")

urlpatterns = router.urls
