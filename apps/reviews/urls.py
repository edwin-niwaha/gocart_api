from rest_framework.routers import DefaultRouter

from .views import ProductRatingViewSet, ReviewViewSet

router = DefaultRouter()
router.register("reviews", ReviewViewSet, basename="reviews")
router.register("ratings", ProductRatingViewSet, basename="ratings")

urlpatterns = router.urls