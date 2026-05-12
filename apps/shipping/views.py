from django.db.models import Q
from rest_framework import permissions, viewsets

from apps.tenants.permissions import IsTenantManager
from .models import DeliveryRate, PickupStation, ShippingMethod
from .serializers import (
    DeliveryRateReadSerializer,
    DeliveryRateWriteSerializer,
    PickupStationReadSerializer,
    PickupStationWriteSerializer,
    ShippingMethodReadSerializer,
    ShippingMethodWriteSerializer,
)


class ShippingMethodViewSet(viewsets.ModelViewSet):
    queryset = ShippingMethod.objects.all().order_by("name")

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ShippingMethodWriteSerializer
        return ShippingMethodReadSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantManager()]


class PickupStationViewSet(viewsets.ModelViewSet):
    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        queryset = PickupStation.objects.all().order_by("city", "area", "name")

        if tenant is None:
            return queryset.none()

        if self.request.method in permissions.SAFE_METHODS:
            return queryset.filter(Q(tenant=tenant) | Q(tenant__isnull=True))

        return queryset.filter(tenant=tenant)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PickupStationWriteSerializer
        return PickupStationReadSerializer

    def get_permissions(self):
        if self.request.method in permissions.SAFE_METHODS:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantManager()]

    def perform_create(self, serializer):
        serializer.save(tenant=getattr(self.request, "tenant", None))


class DeliveryRateViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsTenantManager]

    def get_queryset(self):
        tenant = getattr(self.request, "tenant", None)
        queryset = DeliveryRate.objects.all().order_by(
            "region",
            "city",
            "area",
            "fee",
            "estimated_days",
            "id",
        )

        if tenant is None:
            return queryset.none()

        return queryset.filter(tenant=tenant)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return DeliveryRateWriteSerializer
        return DeliveryRateReadSerializer

    def perform_create(self, serializer):
        serializer.save(tenant=getattr(self.request, "tenant", None))


