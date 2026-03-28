from django.db.models.deletion import ProtectedError
from rest_framework import permissions, status, viewsets
from rest_framework.response import Response

from .models import CustomerAddress
from .serializers import CustomerAddressSerializer
from .services import create_address, delete_address, update_address


class IsAddressOwner(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user and request.user.is_staff:
            return True
        return obj.user == request.user


class CustomerAddressViewSet(viewsets.ModelViewSet):
    serializer_class = CustomerAddressSerializer
    permission_classes = [permissions.IsAuthenticated, IsAddressOwner]

    def get_queryset(self):
        queryset = CustomerAddress.objects.select_related("user").order_by(
            "-is_default", "-created_at"
        )
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def perform_create(self, serializer):
        return create_address(user=self.request.user, **serializer.validated_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        address = self.perform_create(serializer)
        output = self.get_serializer(address)
        headers = self.get_success_headers(output.data)
        return Response(output.data, status=status.HTTP_201_CREATED, headers=headers)

    def perform_update(self, serializer):
        return update_address(instance=self.get_object(), **serializer.validated_data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        address = self.perform_update(serializer)
        output = self.get_serializer(address)
        return Response(output.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()

        try:
            self.perform_destroy(instance)
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ProtectedError:
            return Response(
                {
                    "detail": "This address cannot be deleted because it is linked to existing records."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

    def perform_destroy(self, instance):
        delete_address(instance=instance)