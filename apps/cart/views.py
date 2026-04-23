from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from apps.common.guest_sessions import get_request_guest_session_key
from apps.tenants.permissions import is_platform_admin
from .models import Cart, CartItem
from .serializers import (
    CartItemReadSerializer,
    CartItemWriteSerializer,
    CartReadSerializer,
    CartWriteSerializer,
)
from .services import add_item_to_cart, get_or_create_cart, remove_cart_item, update_cart_item


class IsCartOwner(permissions.BasePermission):
    def has_permission(self, request, view):
        return True

    def has_object_permission(self, request, view, obj):
        if is_platform_admin(request.user):
            return True

        if getattr(request.user, "is_authenticated", False):
            owner = getattr(obj, "user", None)
            if owner is not None:
                return owner == request.user

            cart = getattr(obj, "cart", None)
            if cart is not None:
                return cart.user == request.user

            return False

        guest_session_key = get_request_guest_session_key(request)
        if not guest_session_key:
            return False

        guest_owner = getattr(obj, "guest_session_key", None)
        if guest_owner is not None:
            return guest_owner == guest_session_key

        cart = getattr(obj, "cart", None)
        if cart is not None:
            return cart.guest_session_key == guest_session_key

        owner = getattr(obj, "user", None)
        if owner is not None:
            return owner == request.user

        return False


class CartViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny, IsCartOwner]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = Cart.objects.select_related("user").prefetch_related(
            "items",
            "items__variant",
            "items__variant__product",
            "items__variant__product__category",
        )
        if is_platform_admin(self.request.user):
            return queryset
        if getattr(self.request.user, "is_authenticated", False):
            return queryset.filter(
                user=self.request.user,
                items__variant__tenant=tenant,
            ).distinct()

        guest_session_key = get_request_guest_session_key(self.request)
        if not guest_session_key:
            return queryset.none()

        return queryset.filter(
            user__isnull=True,
            guest_session_key=guest_session_key,
            items__variant__tenant=tenant,
        ).distinct()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CartWriteSerializer
        return CartReadSerializer

    def create(self, request, *args, **kwargs):
        guest_session_key = get_request_guest_session_key(
            request,
            create=not getattr(request.user, "is_authenticated", False),
        )
        cart = get_or_create_cart(
            user=request.user if getattr(request.user, "is_authenticated", False) else None,
            guest_session_key=guest_session_key,
        )
        serializer = CartReadSerializer(cart, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.AllowAny, IsCartOwner]

    def get_queryset(self):
        tenant = self.request.tenant
        queryset = CartItem.objects.select_related(
            "cart",
            "cart__user",
            "variant",
            "variant__product",
            "variant__product__category",
        ).filter(variant__tenant=tenant)
        if is_platform_admin(self.request.user):
            return queryset
        if getattr(self.request.user, "is_authenticated", False):
            return queryset.filter(cart__user=self.request.user)

        guest_session_key = get_request_guest_session_key(self.request)
        if not guest_session_key:
            return queryset.none()

        return queryset.filter(
            cart__user__isnull=True,
            cart__guest_session_key=guest_session_key,
        )

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CartItemWriteSerializer
        return CartItemReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        guest_session_key = get_request_guest_session_key(
            request,
            create=not getattr(request.user, "is_authenticated", False),
        )

        item = add_item_to_cart(
            user=request.user if getattr(request.user, "is_authenticated", False) else None,
            guest_session_key=guest_session_key,
            variant=serializer.validated_data["variant"],
            quantity=serializer.validated_data["quantity"],
            tenant=request.tenant,
        )

        output = CartItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data.get("quantity", instance.quantity)
        item = update_cart_item(item=instance, quantity=quantity, tenant=request.tenant)

        output = CartItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        remove_cart_item(item=instance)
