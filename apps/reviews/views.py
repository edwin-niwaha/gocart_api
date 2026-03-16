from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response

from .models import ProductRating, Review
from .serializers import ProductRatingSerializer, ReviewSerializer
from .services import create_review, delete_review, update_review


class IsReviewOwnerOrReadOnly(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and (request.user.is_staff or obj.user == request.user))


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsReviewOwnerOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["product", "rating"]
    search_fields = ["comment", "product__title", "user__email"]
    ordering_fields = ["created_at", "rating"]

    def get_queryset(self):
        queryset = Review.objects.select_related("user", "product").all()

        mine = self.request.query_params.get("mine") # type: ignore
        if mine in {"1", "true", "True"}:
            if not self.request.user.is_authenticated:
                return queryset.none()
            queryset = queryset.filter(user=self.request.user)

        return queryset

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response(
                {"detail": "Authentication credentials were not provided."},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = create_review(user=request.user, **serializer.validated_data)
        output = self.get_serializer(review)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()

        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        review = update_review(instance=instance, **serializer.validated_data)
        output = self.get_serializer(review)
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        delete_review(instance=instance)


class ProductRatingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductRatingSerializer
    permission_classes = [permissions.AllowAny]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["product"]
    ordering_fields = ["average_rating", "total_reviews"]

    def get_queryset(self):
        return ProductRating.objects.select_related("product").all()