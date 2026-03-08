from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import Cart, CartItem
from .serializers import (
    CartItemReadSerializer,
    CartItemWriteSerializer,
    CartReadSerializer,
    CartWriteSerializer,
)
from .services import add_item_to_cart, get_or_create_cart, remove_cart_item, update_cart_item


class IsCartOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True

        owner = getattr(obj, "user", None)
        if owner is not None:
            return owner == request.user

        cart = getattr(obj, "cart", None)
        if cart is not None:
            return cart.user == request.user

        return False


class CartViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCartOwner]

    def get_queryset(self):
        queryset = Cart.objects.select_related("user").prefetch_related(
            "items",
            "items__product",
            "items__product__category",
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CartWriteSerializer
        return CartReadSerializer

    def create(self, request, *args, **kwargs):
        cart = get_or_create_cart(user=request.user)
        serializer = CartReadSerializer(cart, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsCartOwner]

    def get_queryset(self):
        queryset = CartItem.objects.select_related(
            "cart",
            "cart__user",
            "product",
            "product__category",
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(cart__user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return CartItemWriteSerializer
        return CartItemReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = add_item_to_cart(
            user=request.user,
            product=serializer.validated_data["product"],
            quantity=serializer.validated_data["quantity"],
        )

        output = CartItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        quantity = serializer.validated_data.get("quantity", instance.quantity)
        item = update_cart_item(item=instance, quantity=quantity)

        output = CartItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def perform_destroy(self, instance):
        remove_cart_item(item=instance)