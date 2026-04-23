from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import NotFound, PermissionDenied
from rest_framework.response import Response

from apps.common.views import create_audit_log
from apps.tenants.permissions import IsTenantManager
from apps.tenants.utils import user_is_tenant_staff
from .models import Coupon
from .serializers import CouponApplySerializer, CouponSerializer, CouponValidateSerializer
from .services import apply_coupon_to_order, calculate_coupon_discount, get_valid_coupon


class CouponViewSet(viewsets.ModelViewSet):
    serializer_class = CouponSerializer

    def get_queryset(self):
        return Coupon.objects.prefetch_related("products", "categories").filter(tenant=self.request.tenant).order_by("-created_at")

    def get_permissions(self):
        if self.action in ["list", "retrieve", "validate_coupon"]:
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated(), IsTenantManager()]

    def perform_create(self, serializer):
        coupon = serializer.save(tenant=self.request.tenant)
        create_audit_log(tenant=self.request.tenant, actor=self.request.user, action="coupon.created", summary=f"Coupon {coupon.code} created", target=coupon)

    def perform_update(self, serializer):
        coupon = serializer.save(tenant=self.request.tenant)
        create_audit_log(tenant=self.request.tenant, actor=self.request.user, action="coupon.updated", summary=f"Coupon {coupon.code} updated", target=coupon)

    @action(detail=False, methods=["post"], url_path="validate")
    def validate_coupon(self, request):
        serializer = CouponValidateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        coupon = get_valid_coupon(code=serializer.validated_data["code"], tenant=request.tenant)
        amount = serializer.validated_data["amount"]
        discount = calculate_coupon_discount(coupon=coupon, amount=amount)
        final_amount = amount - discount
        return Response({"code": coupon.code, "discount": discount, "final_amount": final_amount}, status=status.HTTP_200_OK)

    @action(detail=False, methods=["post"], url_path="apply-to-order", permission_classes=[permissions.IsAuthenticated])
    def apply_to_order(self, request):
        serializer = CouponApplySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        from apps.orders.models import Order
        try:
            order = Order.objects.prefetch_related("items", "items__product").get(
                pk=serializer.validated_data["order_id"],
                tenant=request.tenant,
            )
        except Order.DoesNotExist:
            raise NotFound("Order not found.")

        if not user_is_tenant_staff(request.user, getattr(request, "tenant", None)) and order.user != request.user:
            raise PermissionDenied("You cannot apply a coupon to another user's order.")
        result = apply_coupon_to_order(order=order, code=serializer.validated_data["code"])
        return Response({"coupon": result["coupon"].code, "discount": result["discount"], "final_amount": result["final_amount"]}, status=status.HTTP_200_OK)
