from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Inventory, InventoryMovement
from .serializers import InventoryMovementSerializer, InventorySerializer
from .services import (
    decrease_stock,
    get_or_create_inventory,
    increase_stock,
    release_reserved_stock,
    reserve_stock,
)


class InventoryViewSet(viewsets.ModelViewSet):
    queryset = Inventory.objects.select_related("product").order_by("product__title")
    serializer_class = InventorySerializer
    permission_classes = [permissions.IsAdminUser]

    def perform_create(self, serializer):
        inventory = serializer.save()
        inventory.sync_stock_status()
        inventory.save(update_fields=["is_in_stock", "updated_at"])

    def perform_update(self, serializer):
        inventory = serializer.save()
        inventory.sync_stock_status()
        inventory.save(update_fields=["is_in_stock", "updated_at"])

    @action(detail=True, methods=["post"])
    def adjust(self, request, pk=None):
        inventory = self.get_object()

        movement_type = request.data.get("movement_type")
        quantity = int(request.data.get("quantity", 0))
        note = request.data.get("note", "")

        if movement_type == InventoryMovement.MovementType.IN:
            movement = increase_stock(
                product=inventory.product,
                quantity=quantity,
                note=note,
            )
        elif movement_type == InventoryMovement.MovementType.OUT:
            movement = decrease_stock(
                product=inventory.product,
                quantity=quantity,
                note=note,
            )
        elif movement_type == InventoryMovement.MovementType.RESERVED:
            movement = reserve_stock(
                product=inventory.product,
                quantity=quantity,
                note=note,
            )
        elif movement_type == InventoryMovement.MovementType.RELEASED:
            movement = release_reserved_stock(
                product=inventory.product,
                quantity=quantity,
                note=note,
            )
        else:
            return Response(
                {"detail": "Invalid movement_type."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            InventoryMovementSerializer(movement).data,
            status=status.HTTP_201_CREATED,
        )


class InventoryMovementViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = InventoryMovement.objects.select_related(
        "inventory",
        "inventory__product",
    ).order_by("-created_at")
    serializer_class = InventoryMovementSerializer
    permission_classes = [permissions.IsAdminUser]