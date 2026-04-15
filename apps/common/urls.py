from rest_framework.routers import DefaultRouter
from .views import ContactMessageViewSet, NewsletterSubscribeViewSet

router = DefaultRouter()
router.register("contact", ContactMessageViewSet, basename="contact-message")
router.register("newsletter", NewsletterSubscribeViewSet, basename="newsletter")

urlpatterns = router.urls