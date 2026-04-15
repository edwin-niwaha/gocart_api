from __future__ import annotations

import logging

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.cart.models import CartItem
from apps.tenants.utils import user_is_tenant_staff
from .models import Order, OrderItem
from .notifications import queue_order_created_notifications
from .serializers import (
    OrderCheckoutSerializer,
    OrderItemReadSerializer,
    OrderItemWriteSerializer,
    OrderReadSerializer,
    OrderStatusTransitionSerializer,
    OrderWriteSerializer,
)
from .services import add_order_item, create_order, remove_order_item, transition_order_status, update_order_item

logger = logging.getLogger(__name__)


class IsAdminOrOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if user_is_tenant_staff(request.user, getattr(request, "tenant", None)):
            return True
        owner = getattr(obj, "user", None)
        if owner is not None:
            return owner == request.user
        order = getattr(obj, "order", None)
        if order is not None:
            return order.user == request.user
        return False


class OrderViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwner]
    lookup_field = "slug"
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status"]
    search_fields = ["slug", "description"]
    ordering_fields = ["created_at", "total_price", "status"]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = Order.objects.select_related("tenant", "user", "address").prefetch_related(
            "items",
            "items__product",
            "items__variant",
            "status_events",
            "status_events__changed_by",
        ).filter(tenant=tenant)
        if user_is_tenant_staff(self.request.user, tenant):
            return queryset
        return queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "checkout":
            return OrderCheckoutSerializer
        if self.action == "transition_status":
            return OrderStatusTransitionSerializer
        if self.action in {"create", "update", "partial_update"}:
            return OrderWriteSerializer
        return OrderReadSerializer

    @action(detail=False, methods=["post"], url_path="checkout")
    def checkout(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        address = serializer.validated_data["address"]
        description = serializer.validated_data.get("description", "")
        tenant = request.tenant

        cart_items = list(
            CartItem.objects.select_related("cart", "variant", "variant__product")
            .filter(cart__user=request.user, variant__tenant=tenant)
        )

        if not cart_items:
            return Response({"detail": "Your cart is empty for this tenant."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            order = create_order(user=request.user, tenant=tenant, address=address, description=description or "Placed from mobile app")
            for cart_item in cart_items:
                variant = cart_item.variant.__class__.objects.select_for_update().get(id=cart_item.variant.id)
                quantity = cart_item.quantity
                if variant.stock_quantity < quantity:
                    raise Exception(f"Insufficient stock for {variant.product.title} ({variant.name})")
                variant.stock_quantity -= quantity
                variant.save(update_fields=["stock_quantity"])
                add_order_item(order=order, variant=variant, quantity=quantity)
            order.recalculate_total_price()
            CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()
            queue_order_created_notifications(order.id)

        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], url_path="transition-status")
    def transition_status(self, request, slug=None):
        order = self.get_object()
        if not user_is_tenant_staff(request.user, request.tenant):
            return Response({"detail": "Only tenant staff can change order status."}, status=status.HTTP_403_FORBIDDEN)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = transition_order_status(
            order=order,
            new_status=serializer.validated_data["status"],
            changed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )
        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)

    def create(self, request, *args, **kwargs):
        return Response({"detail": "Use the checkout endpoint."}, status=status.HTTP_405_METHOD_NOT_ALLOWED)


class OrderItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwner]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["order", "variant"]
    ordering_fields = ["created_at", "quantity", "unit_price"]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = OrderItem.objects.select_related("tenant", "order", "order__user", "product", "variant").filter(tenant=tenant)
        if user_is_tenant_staff(self.request.user, tenant):
            return queryset
        return queryset.filter(order__user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return OrderItemWriteSerializer
        return OrderItemReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        item = add_order_item(
            order=serializer.validated_data["order"],
            variant=serializer.validated_data["variant"],
            quantity=serializer.validated_data["quantity"],
        )
        output = OrderItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        item = update_order_item(item=instance, **serializer.validated_data)
        output = OrderItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        remove_order_item(item=instance)
