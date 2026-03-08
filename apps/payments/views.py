from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Payment
from .serializers import PaymentReadSerializer, PaymentWriteSerializer
from .services import create_payment, mark_payment_failed, mark_payment_paid


class IsPaymentOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        return bool(request.user and (request.user.is_staff or obj.user == request.user))


class PaymentViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated, IsPaymentOwnerOrAdmin]
    http_method_names = ["get", "post", "patch", "head", "options"]

    def get_queryset(self):
        queryset = Payment.objects.select_related("user", "order").order_by("-created_at")
        if self.request.user.is_staff:
            return queryset
        return queryset.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return PaymentWriteSerializer
        return PaymentReadSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        payment = create_payment(
            user=request.user,
            order=serializer.validated_data["order"],
            provider=serializer.validated_data["provider"],
            amount=serializer.validated_data["amount"],
            currency=serializer.validated_data.get("currency", Payment.Currency.UGX),
        )

        output = PaymentReadSerializer(payment, context=self.get_serializer_context())
        return Response(output.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def mark_paid(self, request, pk=None):
        payment = mark_payment_paid(
            payment=self.get_object(),
            transaction_id=request.data.get("transaction_id", ""),
            provider_response=request.data.get("provider_response", {}),
        )
        return Response(PaymentReadSerializer(payment).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def mark_failed(self, request, pk=None):
        payment = mark_payment_failed(
            payment=self.get_object(),
            provider_response=request.data.get("provider_response", {}),
        )
        return Response(PaymentReadSerializer(payment).data, status=status.HTTP_200_OK)