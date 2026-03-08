from rest_framework.routers import DefaultRouter

from .views import InventoryMovementViewSet, InventoryViewSet

router = DefaultRouter()
router.register("inventory", InventoryViewSet, basename="inventory")
router.register("inventory-movements", InventoryMovementViewSet, basename="inventory-movements")

urlpatterns = router.urls