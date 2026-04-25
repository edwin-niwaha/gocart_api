from django.db.models import Q
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.tenants.permissions import IsTenantManager
from apps.tenants.utils import user_is_tenant_staff
from .models import DeliveryRate, PickupStation, Shipment, ShippingMethod
from .serializers import (
    DeliveryRateReadSerializer,
    DeliveryRateWriteSerializer,
    PickupStationReadSerializer,
    PickupStationWriteSerializer,
    ShipmentReadSerializer,
    ShipmentWriteSerializer,
    ShippingMethodReadSerializer,
    ShippingMethodWriteSerializer,
)
from .services import (
    create_shipment,
    mark_shipment_delivered,
    mark_shipment_in_transit,
    mark_shipment_shipped,
)


class IsShipmentOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        tenant = getattr(request, "tenant", None)
        if tenant is None or obj.order.tenant_id != tenant.id:
            return False
        return bool(request.user and (user_is_tenant_staff(request.user, tenant) or obj.order.user == request.user))


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


class ShipmentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsShipmentOwnerOrAdmin]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = Shipment.objects.select_related(
            "order",
            "order__user",
            "address",
            "shipping_method",
        ).filter(order__tenant=tenant).order_by("-created_at")
        if user_is_tenant_staff(self.request.user, tenant):
            return queryset
        return queryset.filter(order__user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return ShipmentWriteSerializer
        return ShipmentReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        shipment = create_shipment(
            order=serializer.validated_data["order"],
            address=serializer.validated_data["address"],
            shipping_method=serializer.validated_data["shipping_method"],
        )

        output = ShipmentReadSerializer(shipment, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsTenantManager])
    def mark_shipped(self, request, pk=None):
        shipment = mark_shipment_shipped(
            shipment=self.get_object(),
            tracking_number=request.data.get("tracking_number", ""),
        )
        return Response(ShipmentReadSerializer(shipment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsTenantManager])
    def mark_in_transit(self, request, pk=None):
        shipment = mark_shipment_in_transit(shipment=self.get_object())
        return Response(ShipmentReadSerializer(shipment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAuthenticated, IsTenantManager])
    def mark_delivered(self, request, pk=None):
        shipment = mark_shipment_delivered(shipment=self.get_object())
        return Response(ShipmentReadSerializer(shipment).data, status=status.HTTP_200_OK)
