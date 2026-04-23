from django.db.models import Q
from django.utils import timezone

from rest_framework import generics, status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order
from apps.tenants.models import TenantMembership

from .models import Payment
from .serializers import AdminPaymentSerializer


def get_user_active_membership(user, tenant=None):
    memberships = TenantMembership.objects.filter(user=user, is_active=True)

    if tenant is not None:
        memberships = memberships.filter(tenant=tenant)

    return memberships.select_related("tenant").first()


def is_global_admin(user):
    if not user.is_authenticated:
        return False

    # adjust this if your user model uses a different admin field
    return getattr(user, "is_superuser", False) or getattr(user, "user_type", None) == "ADMIN"


class AdminPaymentListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = AdminPaymentSerializer

    def get_queryset(self):
        user = self.request.user
        tenant = getattr(self.request, "tenant", None)

        queryset = Payment.objects.select_related(
            "user", "order", "tenant"
        ).order_by("-created_at")

        # Global admin can see everything
        if is_global_admin(user):
            pass
        else:
            membership = get_user_active_membership(user, tenant=tenant)
            allowed_roles = {
                TenantMembership.Role.SUPER_ADMIN,
                TenantMembership.Role.TENANT_OWNER,
                TenantMembership.Role.TENANT_ADMIN,
                TenantMembership.Role.MANAGER,
            }

            if not membership or membership.role not in allowed_roles:
                return Payment.objects.none()

            # Tenant-scoped admin/manager sees only their tenant's payments
            queryset = queryset.filter(tenant=membership.tenant)

        status_value = self.request.query_params.get("status")
        provider = self.request.query_params.get("provider")
        search = self.request.query_params.get("search")

        if status_value:
            queryset = queryset.filter(status=status_value)

        if provider:
            queryset = queryset.filter(provider=provider)

        if search:
            queryset = queryset.filter(
                Q(reference__icontains=search)
                | Q(transaction_id__icontains=search)
                | Q(external_id__icontains=search)
                | Q(phone_number__icontains=search)
                | Q(order__slug__icontains=search)
                | Q(user__email__icontains=search)
                | Q(user__username__icontains=search)
                | Q(tenant__name__icontains=search)
                | Q(tenant__slug__icontains=search)
            )

        return queryset


class AdminPaymentDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_payment(self, request, pk):
        user = request.user
        tenant = getattr(request, "tenant", None)

        queryset = Payment.objects.select_related("order", "tenant", "user")

        # Global admin can access any payment
        if is_global_admin(user):
            return queryset.filter(pk=pk).first()

        membership = get_user_active_membership(user, tenant=tenant)
        allowed_roles = {
            TenantMembership.Role.SUPER_ADMIN,
            TenantMembership.Role.TENANT_OWNER,
            TenantMembership.Role.TENANT_ADMIN,
            TenantMembership.Role.MANAGER,
        }

        if not membership or membership.role not in allowed_roles:
            return None

        return queryset.filter(pk=pk, tenant=membership.tenant).first()

    def patch(self, request, pk):
        payment = self.get_payment(request, pk)
        if not payment:
            raise NotFound("Payment not found.")

        serializer = AdminPaymentSerializer(
            payment,
            data=request.data,
            partial=True,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        previous_status = payment.status
        updated_payment = serializer.save()

        if (
            updated_payment.status == Payment.Status.PAID
            and previous_status != Payment.Status.PAID
            and not updated_payment.paid_at
        ):
            updated_payment.paid_at = timezone.now()
            updated_payment.save(update_fields=["paid_at", "updated_at"])

        if (
            updated_payment.order_id
            and previous_status != Payment.Status.PAID
            and updated_payment.status == Payment.Status.PAID
        ):
            updated_payment.order.status = Order.Status.PAID
            updated_payment.order.save(update_fields=["status", "updated_at"])

        return Response(
            AdminPaymentSerializer(updated_payment, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
