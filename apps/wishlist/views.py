from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from apps.tenants.permissions import is_platform_admin
from .models import Wishlist, WishlistItem
from .serializers import (
    WishlistItemReadSerializer,
    WishlistItemWriteSerializer,
    WishlistReadSerializer,
    WishlistWriteSerializer,
)
from .services import add_item_to_wishlist, get_or_create_wishlist, remove_wishlist_item


class IsWishlistOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if is_platform_admin(request.user):
            return True

        owner = getattr(obj, "user", None)
        if owner is not None:
            return owner == request.user

        wishlist = getattr(obj, "wishlist", None)
        if wishlist is not None:
            return wishlist.user == request.user

        return False


class WishlistViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsWishlistOwner]

    def get_queryset(self):
        queryset = Wishlist.objects.select_related("user").prefetch_related(
            "items",
            "items__product",
            "items__product__category",
        )
        if is_platform_admin(self.request.user):
            return queryset
        return queryset.filter(user=self.request.user, items__product__tenant=self.request.tenant).distinct()

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WishlistWriteSerializer
        return WishlistReadSerializer

    def create(self, request, *args, **kwargs):
        wishlist = get_or_create_wishlist(user=request.user)
        serializer = WishlistReadSerializer(wishlist, context=self.get_serializer_context())
        return Response(serializer.data, status=status.HTTP_200_OK)


class WishlistItemViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsWishlistOwner]

    def get_queryset(self):
        queryset = WishlistItem.objects.select_related(
            "wishlist",
            "wishlist__user",
            "product",
            "product__category",
        )
        if is_platform_admin(self.request.user):
            return queryset
        return queryset.filter(wishlist__user=self.request.user, product__tenant=self.request.tenant)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WishlistItemWriteSerializer
        return WishlistItemReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        item = add_item_to_wishlist(
            user=request.user,
            product=serializer.validated_data["product"],
        )
        output = WishlistItemReadSerializer(item, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        remove_wishlist_item(item=instance)
