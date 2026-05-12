from django.db.models import Prefetch
from django_filters.rest_framework import DjangoFilterBackend
import json
from rest_framework import filters, status, viewsets
from rest_framework.response import Response

from apps.tenants.permissions import IsTenantAdminOrReadOnly
from apps.tenants.utils import user_is_tenant_staff
from .models import Category, Product, ProductImage, ProductVariant
from .serializers import (
    CategorySerializer,
    ProductSerializer,
    ProductVariantSerializer,
)
from .services import create_category, create_product, update_category, update_product


def normalize_product_payload(request):
    if hasattr(request, "POST") and request.POST:
        data = {
            key: values[-1] if len(values) == 1 else values
            for key, values in request.POST.lists()
        }
    else:
        data = dict(request.data)

    hero_image = request.FILES.get("hero_image")
    if hero_image is not None:
        data["hero_image"] = hero_image

    images_payload = data.pop("images_payload", None)
    if images_payload:
        raw_payload = images_payload[0] if isinstance(images_payload, list) else images_payload
        image_items = json.loads(raw_payload or "[]")

        for index, item in enumerate(image_items):
            uploaded_image = request.FILES.get(f"image_file_{index}")
            if uploaded_image is not None:
                item["image"] = uploaded_image

        data["images"] = image_items

    variants_payload = data.pop("variants_payload", None)
    if variants_payload:
        raw_payload = variants_payload[0] if isinstance(variants_payload, list) else variants_payload
        data["variants"] = json.loads(raw_payload or "[]")

    return data


class CategoryViewSet(viewsets.ModelViewSet):
    serializer_class = CategorySerializer
    permission_classes = [IsTenantAdminOrReadOnly]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["is_active"]
    search_fields = ["name", "slug"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = Category.objects.filter(tenant=tenant).order_by("name")

        if user_is_tenant_staff(self.request.user, tenant):
            return queryset

        return queryset.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        category = create_category(tenant=request.tenant, **serializer.validated_data)
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
    permission_classes = [IsTenantAdminOrReadOnly]
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
        tenant = self.request.tenant

        base_queryset = Product.objects.select_related(
            "tenant",
            "category",
            "product_rating",
        ).filter(tenant=tenant).order_by("-created_at")

        if user_is_tenant_staff(self.request.user, tenant):
            return base_queryset.prefetch_related(
                "variants",
                "images",
            )

        active_variants = Prefetch(
            "variants",
            queryset=ProductVariant.objects.filter(
                tenant=tenant,
                is_active=True,
            ).order_by(
                "sort_order",
                "price",
                "id",
            ),
        )

        active_images = Prefetch(
            "images",
            queryset=ProductImage.objects.filter(
                tenant=tenant,
                is_active=True,
            ).order_by(
                "sort_order",
                "id",
            ),
        )

        return (
            base_queryset.prefetch_related(active_variants, active_images)
            .filter(
                is_active=True,
                category__is_active=True,
                variants__tenant=tenant,
                variants__is_active=True,
            )
            .distinct()
        )


    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=normalize_product_payload(request))
        serializer.is_valid(raise_exception=True)

        product = create_product(tenant=request.tenant, **serializer.validated_data)
        output = self.get_serializer(product)
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance,
            data=normalize_product_payload(request),
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)

        product = update_product(instance=instance, **serializer.validated_data)
        output = self.get_serializer(product)
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)


class ProductVariantViewSet(viewsets.ModelViewSet):
    serializer_class = ProductVariantSerializer
    permission_classes = [IsTenantAdminOrReadOnly]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["product", "is_active"]
    search_fields = ["name", "sku", "product__title", "product__slug"]
    ordering_fields = ["created_at", "price", "stock_quantity", "sort_order"]
    ordering = ["sort_order", "price", "id"]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = ProductVariant.objects.select_related("tenant", "product").filter(
            tenant=tenant
        )

        product_slug = self.request.query_params.get("product_slug")
        if product_slug:
            queryset = queryset.filter(product__slug=product_slug)

        if user_is_tenant_staff(self.request.user, tenant):
            return queryset

        return queryset.filter(is_active=True, product__is_active=True)

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["require_product"] = self.action == "create"
        return context

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
