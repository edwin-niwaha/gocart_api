from __future__ import annotations

import logging

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.cart.models import CartItem
from apps.payments.models import Payment
from apps.tenants.utils import user_is_tenant_staff
from .models import Order, OrderItem
from .notifications import queue_order_created_notifications
from .serializers import (
    OrderCheckoutSerializer,
    OrderItemReadSerializer,
    OrderReadSerializer,
    OrderStatusTransitionSerializer,
    OrderWriteSerializer,
)
from .services import add_order_item, create_order, transition_order_status

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
        tenant = self.request.tenant  # type: ignore
        queryset = (
            Order.objects.select_related("tenant", "user", "address")
            .prefetch_related(
                "items",
                "items__product",
                "items__variant",
                "status_events",
                "status_events__changed_by",
            )
            .filter(tenant=tenant)
        )

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
        payment_method = serializer.validated_data.get(
            "payment_method",
            Payment.Provider.CASH,
        )
        tenant = request.tenant

        cart_items = list(
            CartItem.objects.select_related("cart", "variant", "variant__product").filter(
                cart__user=request.user,
                variant__tenant=tenant,
            )
        )

        if not cart_items:
            return Response(
                {"detail": "Your cart is empty for this tenant."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            order_status = (
                Order.Status.PENDING
                if payment_method == Payment.Provider.CASH
                else Order.Status.AWAITING_PAYMENT
            )

            order = create_order(
                user=request.user,
                tenant=tenant,
                address=address,
                description=description or "Placed from checkout",
                status=order_status,
            )

            for cart_item in cart_items:
                variant = cart_item.variant.__class__.objects.select_for_update().get(
                    id=cart_item.variant.id
                )
                quantity = cart_item.quantity

                if variant.stock_quantity < quantity:
                    return Response(
                        {
                            "detail": f"Insufficient stock for {variant.product.title} ({variant.name})"
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                variant.stock_quantity -= quantity
                variant.save(update_fields=["stock_quantity"])
                add_order_item(order=order, variant=variant, quantity=quantity)

            order.recalculate_total_price()

            payment_status = (
                Payment.Status.PENDING
                if payment_method == Payment.Provider.CASH
                else Payment.Status.PROCESSING
            )

            payment_note = (
                "Pay on delivery selected at checkout"
                if payment_method == Payment.Provider.CASH
                else f"{payment_method} selected at checkout"
            )

            payment = Payment.objects.create(
                tenant=tenant,
                user=request.user,
                order=order,
                provider=payment_method,
                amount=order.total_price,
                currency=Payment.Currency.UGX,
                status=payment_status,
                provider_response={
                    "payment_method": payment_method,
                    "payment_note": payment_note,
                },
            )

            CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()
            queue_order_created_notifications(order.id)

        output = OrderReadSerializer(order, context=self.get_serializer_context())
        return Response(
            {
                "order": output.data,
                "payment_reference": payment.reference,
                "payment_status": payment.status,
                "payment_provider": payment.provider,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="transition-status")
    def transition_status(self, request, slug=None, *args, **kwargs):
        order = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated = transition_order_status(
            order=order,
            new_status=serializer.validated_data["status"],
            changed_by=request.user,
            note=serializer.validated_data.get("note", ""),
        )

        return Response(
            OrderReadSerializer(updated, context=self.get_serializer_context()).data,
            status=status.HTTP_200_OK,
        )


class OrderItemViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    permission_classes = [permissions.IsAuthenticated, IsAdminOrOwner]
    serializer_class = OrderItemReadSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["order", "product", "variant"]
    search_fields = ["product_title", "variant_name", "variant_sku", "order__slug"]
    ordering_fields = ["created_at", "quantity", "unit_price"]

    def get_queryset(self):
        tenant = self.request.tenant  # type: ignore
        queryset = (
            OrderItem.objects.select_related("tenant", "order", "product", "variant")
            .filter(tenant=tenant)
        )

        if user_is_tenant_staff(self.request.user, tenant):
            return queryset
        return queryset.filter(order__user=self.request.user)