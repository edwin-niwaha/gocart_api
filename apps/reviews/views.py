from django.db.models import Prefetch
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response

from apps.products.models import Product
from .models import ProductRating, Review
from .serializers import ProductRatingSerializer, ReviewSerializer
from .services import create_review, delete_review, update_review


class ReviewViewSet(viewsets.ModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        queryset = (
            Review.objects.select_related("user", "product")
            .filter(user=self.request.user)
            .order_by("-created_at")
        )
        if tenant is not None:
            queryset = queryset.filter(product__tenant=tenant)

        product_id = self.request.query_params.get("product")
        product_slug = self.request.query_params.get("product_slug")

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if product_slug:
            queryset = queryset.filter(product__slug=product_slug)

        return queryset

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        review = create_review(
            user=request.user,
            **serializer.validated_data,
        )

        output_serializer = self.get_serializer(review)
        headers = self.get_success_headers(output_serializer.data)
        return Response(
            output_serializer.data,
            status=status.HTTP_201_CREATED,
            headers=headers,
        )

    def perform_update(self, serializer):
        serializer.instance = update_review(
            instance=self.get_object(),
            **serializer.validated_data,
        )

    def perform_destroy(self, instance):
        delete_review(instance=instance)


class ProductReviewViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ReviewSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        queryset = Review.objects.select_related("user", "product").order_by("-created_at")
        if tenant is not None:
            queryset = queryset.filter(product__tenant=tenant)

        product_id = self.request.query_params.get("product")
        product_slug = self.request.query_params.get("product_slug")

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if product_slug:
            queryset = queryset.filter(product__slug=product_slug)

        return queryset


class ProductRatingViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = ProductRatingSerializer
    permission_classes = [AllowAny]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        queryset = ProductRating.objects.select_related("product").order_by("-updated_at")
        if tenant is not None:
            queryset = queryset.filter(product__tenant=tenant)

        product_id = self.request.query_params.get("product")
        product_slug = self.request.query_params.get("product_slug")

        if product_id:
            queryset = queryset.filter(product_id=product_id)

        if product_slug:
            queryset = queryset.filter(product__slug=product_slug)

        return queryset
