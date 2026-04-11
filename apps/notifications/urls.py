from rest_framework.routers import DefaultRouter

from .views import NotificationViewSet, DeviceTokenViewSet

router = DefaultRouter()
router.register("notifications", NotificationViewSet, basename="notifications")
router.register("device-tokens", DeviceTokenViewSet, basename="device-tokens")

urlpatterns = router.urls