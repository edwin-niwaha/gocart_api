from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import Coupon
from .serializers import CouponSerializer, CouponValidateSerializer
from .services import apply_coupon_to_order, calculate_coupon_discount, get_valid_coupon


class CouponViewSet(viewsets.ModelViewSet):
    queryset = Coupon.objects.prefetch_related("products", "categories").order_by("-created_at")
    serializer_class = CouponSerializer

    def get_permissions(self):
        if self.action in ["list", "retrieve", "validate_coupon"]:
            return [permissions.AllowAny()]
        return [permissions.IsAdminUser()]

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_coupon(self, request):
        serializer = CouponValidateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        coupon = get_valid_coupon(code=serializer.validated_data["code"]) # type: ignore
        amount = serializer.validated_data["amount"] # type: ignore
        discount = calculate_coupon_discount(coupon=coupon, amount=amount)
        final_amount = amount - discount

        return Response(
            {
                "code": coupon.code,
                "discount": discount,
                "final_amount": final_amount,
            },
            status=status.HTTP_200_OK,
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="apply-to-order",
        permission_classes=[permissions.IsAuthenticated],
    )
    def apply_to_order(self, request):
        code = request.data.get("code", "")
        order = getattr(request, "order", None)

        order_id = request.data.get("order_id")
        if order is None:
            from apps.orders.models import Order

            try:
                order = Order.objects.prefetch_related("items", "items__product").get(pk=order_id)
            except Order.DoesNotExist:
                return Response(
                    {"detail": "Order not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )

        if not request.user.is_staff and order.user != request.user:
            return Response(
                {"detail": "You cannot apply a coupon to another user's order."},
                status=status.HTTP_403_FORBIDDEN,
            )

        result = apply_coupon_to_order(order=order, code=code)

        return Response(
            {
                "coupon": result["coupon"].code,
                "discount": result["discount"],
                "final_amount": result["final_amount"],
            },
            status=status.HTTP_200_OK,
        )