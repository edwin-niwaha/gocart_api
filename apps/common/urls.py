from rest_framework.routers import DefaultRouter
from .views import ContactMessageViewSet

router = DefaultRouter()
router.register("contact", ContactMessageViewSet, basename="contact-message")

urlpatterns = router.urls