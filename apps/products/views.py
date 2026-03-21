from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response

from .models import Category, Product, ProductVariant
from .serializers import CategorySerializer, ProductSerializer
from .services import create_category, create_product, update_category, update_product


class IsAdminOrReadOnly(permissions.BasePermission):
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return bool(request.user and request.user.is_staff)


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        queryset = Category.objects.all().order_by("name")

        if self.request.user and self.request.user.is_staff: # type: ignore
            return queryset

        return queryset.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category = create_category(**serializer.validated_data)
        output = self.get_serializer(category)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        category = update_category(instance=instance, **serializer.validated_data)
        output = self.get_serializer(category)
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class ProductViewSet(viewsets.ModelViewSet):
    serializer_class = ProductSerializer
    permission_classes = [IsAdminOrReadOnly]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["category", "is_active", "is_featured"]
    search_fields = [
        "title",
        "slug",
        "description",
        "category__name",
        "category__slug",
        "variants__name",
        "variants__sku",
    ]
    ordering_fields = ["created_at", "title"]
    ordering = ["-created_at"]

    def get_queryset(self):
        base_queryset = Product.objects.select_related(
            "category",
            "product_rating",
        ).order_by("-created_at")

        if self.request.user and self.request.user.is_staff: # type: ignore
            return base_queryset.prefetch_related("variants")

        active_variants = Prefetch(
            "variants",
            queryset=ProductVariant.objects.filter(is_active=True).order_by(
                "sort_order",
                "price",
                "id",
            ),
        )

        return (
            base_queryset.prefetch_related(active_variants)
            .filter(
                is_active=True,
                category__is_active=True,
                variants__is_active=True,
            )
            .distinct()
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        product = create_product(**serializer.validated_data)
        output = self.get_serializer(product)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        product = update_product(instance=instance, **serializer.validated_data)
        output = self.get_serializer(product)
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)