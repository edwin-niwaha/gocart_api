from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.response import Response

from .models import Order, OrderItem
from .serializers import (
    OrderItemReadSerializer,
    OrderItemWriteSerializer,
    OrderReadSerializer,
    OrderWriteSerializer,
)
from .services import add_order_item, create_order, remove_order_item, update_order_item


class IsAdminOrOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
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
        queryset = Order.objects.select_related("user").prefetch_related(
            "items",
            "items__product",
            "items__variant",
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return OrderWriteSerializer
        return OrderReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order = create_order(user=request.user, **serializer.validated_data)
        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)


class OrderItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwner]
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ["order", "product", "variant"]
    ordering_fields = ["created_at", "quantity"]

    def get_queryset(self):
        queryset = OrderItem.objects.select_related(
            "order",
            "product",
            "variant",
            "order__user",
        )
        if self.request.user.is_staff:
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