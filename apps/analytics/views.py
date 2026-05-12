from __future__ import annotations

from decimal import Decimal

from django.db.models import Count, DecimalField, F, Min, Q, Sum
from django.db.models.functions import Coalesce
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.orders.models import Order, OrderItem
from apps.payments.models import Payment
from apps.products.models import ProductVariant
from apps.tenants.permissions import IsTenantManager

from .serializers import DashboardSummaryQuerySerializer


MONEY_FIELD = DecimalField(max_digits=12, decimal_places=2)
ZERO = Decimal("0.00")


def money(value) -> str:
    return str((value or ZERO).quantize(ZERO))


class AdminDashboardSummaryView(APIView):
    permission_classes = [IsAuthenticated, IsTenantManager]

    def get(self, request):
        query = DashboardSummaryQuerySerializer(
            data=request.query_params,
            context={"tenant": request.tenant},
        )
        query.is_valid(raise_exception=True)
        params = query.validated_data
        tenant = request.tenant
        start_at = params["start_at"]
        end_at = params["end_at"]
        low_stock_threshold = params["low_stock_threshold"]

        orders = Order.objects.filter(
            tenant=tenant,
            created_at__gte=start_at,
            created_at__lte=end_at,
        )
        payments = Payment.objects.filter(
            tenant=tenant,
            created_at__gte=start_at,
            created_at__lte=end_at,
        )
        variants = ProductVariant.objects.select_related("product").filter(tenant=tenant)

        order_count = orders.count()
        gross_order_value = orders.aggregate(total=Coalesce(Sum("total_price"), ZERO, output_field=MONEY_FIELD))["total"]
        average_order_value = gross_order_value / order_count if order_count else ZERO

        orders_by_status = {status: 0 for status, _ in Order.Status.choices}
        for row in orders.values("status").annotate(count=Count("id")):
            orders_by_status[row["status"]] = row["count"]

        payments_by_status = {
            status: {"count": 0, "amount": money(ZERO)}
            for status, _ in Payment.Status.choices
        }
        for row in payments.values("status").annotate(
            count=Count("id"),
            amount=Coalesce(Sum("amount"), ZERO, output_field=MONEY_FIELD),
        ):
            payments_by_status[row["status"]] = {
                "count": row["count"],
                "amount": money(row["amount"]),
            }

        payments_by_provider = {
            row["provider"]: {
                "count": row["count"],
                "amount": money(row["amount"]),
            }
            for row in payments.values("provider").annotate(
                count=Count("id"),
                amount=Coalesce(Sum("amount"), ZERO, output_field=MONEY_FIELD),
            )
        }

        collected_revenue = payments.filter(status=Payment.Status.PAID).aggregate(
            total=Coalesce(Sum("amount"), ZERO, output_field=MONEY_FIELD)
        )["total"]
        refunded_revenue = payments.filter(status=Payment.Status.REFUNDED).aggregate(
            total=Coalesce(Sum("amount"), ZERO, output_field=MONEY_FIELD)
        )["total"]
        outstanding_revenue = orders.filter(
            status__in=[Order.Status.PENDING, Order.Status.AWAITING_PAYMENT]
        ).aggregate(total=Coalesce(Sum("total_price"), ZERO, output_field=MONEY_FIELD))["total"]

        first_orders = (
            Order.objects.filter(tenant=tenant)
            .values("user_id")
            .annotate(first_order_at=Min("created_at"))
            .filter(first_order_at__gte=start_at, first_order_at__lte=end_at)
        )

        inventory = variants.aggregate(
            total_variants=Count("id"),
            active_variants=Count("id", filter=Q(is_active=True)),
            total_units_on_hand=Coalesce(Sum("stock_quantity"), 0),
            out_of_stock=Count("id", filter=Q(is_active=True, stock_quantity=0)),
            low_stock=Count(
                "id",
                filter=Q(
                    is_active=True,
                    stock_quantity__gt=0,
                    stock_quantity__lte=low_stock_threshold,
                ),
            ),
        )

        low_stock_variants = [
            {
                "id": variant.id,
                "product_id": variant.product_id,
                "product_title": variant.product.title,
                "name": variant.name,
                "sku": variant.sku,
                "stock_quantity": variant.stock_quantity,
                "threshold": low_stock_threshold,
            }
            for variant in variants.filter(
                is_active=True,
                stock_quantity__lte=low_stock_threshold,
            )
            .order_by("stock_quantity", "product__title", "name")[:10]
        ]

        top_products = [
            {
                "product_id": row["product_id"],
                "product_title": row["product_title"],
                "units_sold": row["units_sold"],
                "gross_sales": money(row["gross_sales"]),
            }
            for row in (
                OrderItem.objects.filter(
                    tenant=tenant,
                    order__created_at__gte=start_at,
                    order__created_at__lte=end_at,
                )
                .exclude(order__status__in=[Order.Status.CANCELLED, Order.Status.REFUNDED])
                .values("product_id", "product_title")
                .annotate(
                    units_sold=Coalesce(Sum("quantity"), 0),
                    gross_sales=Coalesce(
                        Sum(F("quantity") * F("unit_price"), output_field=MONEY_FIELD),
                        ZERO,
                        output_field=MONEY_FIELD,
                    ),
                )
                .order_by("-units_sold", "-gross_sales")[:5]
            )
        ]

        recent_orders = [
            {
                "id": order.id,
                "slug": order.slug,
                "status": order.status,
                "total_price": money(order.total_price),
                "customer_email": order.user.email if order.user_id else order.guest_email,
                "created_at": order.created_at.isoformat(),
            }
            for order in orders.select_related("user").order_by("-created_at")[:10]
        ]

        return Response(
            {
                "range": {
                    "date_from": params["date_from"].isoformat(),
                    "date_to": params["date_to"].isoformat(),
                    "start_at": start_at.isoformat(),
                    "end_at": end_at.isoformat(),
                },
                "orders": {
                    "total": order_count,
                    "open": orders.filter(
                        status__in=[
                            Order.Status.PENDING,
                            Order.Status.AWAITING_PAYMENT,
                            Order.Status.PROCESSING,
                            Order.Status.PAID,
                            Order.Status.SHIPPED,
                        ]
                    ).count(),
                    "average_order_value": money(average_order_value),
                    "by_status": orders_by_status,
                },
                "revenue": {
                    "gross_order_value": money(gross_order_value),
                    "collected": money(collected_revenue),
                    "refunded": money(refunded_revenue),
                    "outstanding": money(outstanding_revenue),
                },
                "payments": {
                    "by_status": payments_by_status,
                    "by_provider": payments_by_provider,
                },
                "customers": {
                    "unique_buyers": orders.values("user_id").distinct().count(),
                    "new_buyers": first_orders.count(),
                },
                "fulfillment": {
                    "paid_unfulfilled_orders": orders.filter(
                        status__in=[Order.Status.PAID, Order.Status.PROCESSING]
                    ).count(),
                    "shipped_orders": orders.filter(status=Order.Status.SHIPPED).count(),
                    "delivered_orders": orders.filter(status=Order.Status.DELIVERED).count(),
                },
                "inventory": {
                    "total_variants": inventory["total_variants"],
                    "active_variants": inventory["active_variants"],
                    "total_units_on_hand": inventory["total_units_on_hand"],
                    "out_of_stock": inventory["out_of_stock"],
                    "low_stock": inventory["low_stock"],
                    "low_stock_threshold": low_stock_threshold,
                },
                "low_stock_variants": low_stock_variants,
                "top_products": top_products,
                "recent_orders": recent_orders,
            }
        )
