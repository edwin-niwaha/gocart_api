from __future__ import annotations

import logging
import re
from decimal import Decimal

from django.db import transaction
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, mixins, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.cart.models import Cart, CartItem
from apps.payments.models import Payment
from apps.promotions.services import apply_coupon_to_order, increment_coupon_usage
from apps.tenants.permissions import IsTenantStaff
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
IDEMPOTENCY_KEY_PATTERN = re.compile(r"^[A-Za-z0-9._:-]{8,200}$")


def get_idempotency_key(request) -> str:
    key = request.headers.get("Idempotency-Key", "").strip()
    if not key:
        return ""
    if not IDEMPOTENCY_KEY_PATTERN.fullmatch(key):
        raise ValidationError({"idempotency_key": "Invalid idempotency key."})
    return key


def build_checkout_response(*, order: Order, payment: Payment, request, status_code):
    output = OrderReadSerializer(order, context={"request": request})
    return Response(
        {
            "order": output.data,
            "payment_reference": payment.reference,
            "payment_status": payment.status,
            "payment_provider": payment.provider,
        },
        status=status_code,
    )


def get_existing_checkout_payment(*, request, tenant, idempotency_key: str):
    if not idempotency_key:
        return None

    return (
        Payment.objects.select_related("order")
        .filter(
            tenant=tenant,
            user=request.user,
            provider_response__idempotency_key=idempotency_key,
            order__isnull=False,
        )
        .first()
    )


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

    def perform_create(self, serializer):
        serializer.save(user=self.request.user, tenant=self.request.tenant)

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
        shipping_method = serializer.validated_data.get("shipping_method")
        coupon_code = serializer.validated_data.get("coupon_code", "")
        tenant = request.tenant
        idempotency_key = get_idempotency_key(request)

        existing_payment = get_existing_checkout_payment(
            request=request,
            tenant=tenant,
            idempotency_key=idempotency_key,
        )
        if existing_payment is not None:
            return build_checkout_response(
                order=existing_payment.order,
                payment=existing_payment,
                request=request,
                status_code=status.HTTP_200_OK,
            )

        with transaction.atomic():
            cart = Cart.objects.select_for_update().filter(user=request.user).first()
            if cart is None:
                raise ValidationError({"detail": "Your cart is empty for this tenant."})

            existing_payment = get_existing_checkout_payment(
                request=request,
                tenant=tenant,
                idempotency_key=idempotency_key,
            )
            if existing_payment is not None:
                return build_checkout_response(
                    order=existing_payment.order,
                    payment=existing_payment,
                    request=request,
                    status_code=status.HTTP_200_OK,
                )

            cart_items = list(
                CartItem.objects.select_for_update()
                .select_related("cart", "variant", "variant__product")
                .filter(
                    cart=cart,
                    variant__tenant=tenant,
                )
                .order_by("id")
            )

            if not cart_items:
                raise ValidationError({"detail": "Your cart is empty for this tenant."})

            locked_variants = {}
            for cart_item in cart_items:
                variant = (
                    cart_item.variant.__class__.objects.select_related("product")
                    .select_for_update()
                    .get(id=cart_item.variant.id, tenant=tenant)
                )
                quantity = cart_item.quantity

                if variant.stock_quantity < quantity:
                    raise ValidationError(
                        {
                            "detail": f"Insufficient stock for {variant.product.title} ({variant.name})"
                        }
                    )

                locked_variants[cart_item.id] = variant

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
                variant = locked_variants[cart_item.id]
                quantity = cart_item.quantity

                variant.stock_quantity -= quantity
                variant.save(update_fields=["stock_quantity"])
                add_order_item(
                    order=order,
                    variant=variant,
                    quantity=quantity,
                    unit_price=cart_item.unit_price,
                )

            items_subtotal = order.recalculate_total_price()
            discount_amount = Decimal("0.00")
            applied_coupon = None

            if coupon_code:
                coupon_result = apply_coupon_to_order(order=order, code=coupon_code)
                applied_coupon = coupon_result["coupon"]
                discount_amount = coupon_result["discount"]
                increment_coupon_usage(coupon=applied_coupon)

            shipping_fee = shipping_method.fee if shipping_method is not None else Decimal("0.00")
            final_total = max(items_subtotal - discount_amount, Decimal("0.00")) + shipping_fee
            order.total_price = final_total
            order.save(update_fields=["total_price", "updated_at"])

            checkout_summary = {
                "items_subtotal": str(items_subtotal),
                "discount": str(discount_amount),
                "shipping": str(shipping_fee),
                "total": str(final_total),
                "coupon_code": applied_coupon.code if applied_coupon is not None else "",
                "shipping_method_id": shipping_method.id if shipping_method is not None else None,
            }

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
                    "idempotency_key": idempotency_key,
                    "checkout_summary": checkout_summary,
                },
            )

            CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()
            queue_order_created_notifications(order.id)
            logger.info(
                "Checkout created order_id=%s user_id=%s tenant_id=%s payment_reference=%s request_id=%s",
                order.id,
                request.user.id,
                getattr(tenant, "id", None),
                payment.reference,
                getattr(request, "id", ""),
            )

        return build_checkout_response(
            order=order,
            payment=payment,
            request=request,
            status_code=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["post"],
        url_path="transition-status",
        permission_classes=[permissions.IsAuthenticated, IsTenantStaff],
    )
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
