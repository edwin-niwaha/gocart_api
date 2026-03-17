from rest_framework.routers import DefaultRouter

from .views import ProductRatingViewSet, ProductReviewViewSet, ReviewViewSet

app_name = "reviews"

router = DefaultRouter()
router.register(r"reviews", ReviewViewSet, basename="review")
router.register(r"product-reviews", ProductReviewViewSet, basename="product-review")
router.register(r"ratings", ProductRatingViewSet, basename="product-rating")

urlpatterns = router.urls