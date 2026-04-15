from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.addresses.models import CustomerAddress
from apps.cart.models import CartItem
from apps.orders.models import Order
from apps.orders.serializers import OrderReadSerializer
from apps.orders.services import add_order_item, create_order, transition_order_status
from .models import Payment
from .serializers import MTNInitiatePaymentSerializer, PaymentStatusSerializer
from .services import initiate_mtn_payment, refresh_mtn_payment_status, user_has_cart_items


class MTNInitiatePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = MTNInitiatePaymentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        if not user_has_cart_items(request.user, request.tenant):
            return Response({"detail": "Your cart is empty."}, status=status.HTTP_400_BAD_REQUEST)
        address = serializer.context["address_instance"]
        phone_number = serializer.validated_data["phone_number"]
        payment = initiate_mtn_payment(user=request.user, phone_number=phone_number, address=address, tenant=request.tenant)
        return Response({
            "reference": payment.reference,
            "external_id": payment.external_id,
            "status": payment.status,
            "amount": payment.amount,
            "currency": payment.currency,
        }, status=status.HTTP_201_CREATED)


class PaymentStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, reference):
        try:
            payment = Payment.objects.get(reference=reference, user=request.user, tenant=request.tenant)
        except Payment.DoesNotExist:
            return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)
        if payment.provider == Payment.Provider.MTN:
            payment = refresh_mtn_payment_status(payment)
        return Response(PaymentStatusSerializer(payment).data, status=status.HTTP_200_OK)


class FinalizePaidOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, reference):
        with transaction.atomic():
            try:
                payment = Payment.objects.select_for_update().select_related("order").get(
                    reference=reference,
                    user=request.user,
                    tenant=request.tenant,
                )
            except Payment.DoesNotExist:
                return Response({"detail": "Payment not found."}, status=status.HTTP_404_NOT_FOUND)

            if payment.provider == Payment.Provider.MTN:
                payment = refresh_mtn_payment_status(payment)
            if payment.status != Payment.Status.PAID:
                return Response({"detail": "Payment is not successful yet."}, status=status.HTTP_400_BAD_REQUEST)
            if payment.order_id:
                output = OrderReadSerializer(payment.order, context={"request": request})
                return Response({"order": output.data, "payment_reference": payment.reference}, status=status.HTTP_200_OK)

            address_id = payment.provider_response.get("address_id")
            if not address_id:
                return Response({"detail": "Address information missing from payment."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                address = CustomerAddress.objects.get(id=address_id, user=request.user)
            except CustomerAddress.DoesNotExist:
                return Response({"detail": "Address not found."}, status=status.HTTP_400_BAD_REQUEST)

            cart_items = list(
                CartItem.objects.select_related("cart", "variant", "variant__product")
                .filter(cart__user=request.user, variant__tenant=request.tenant)
            )
            if not cart_items:
                return Response({"detail": "Cart is empty."}, status=status.HTTP_400_BAD_REQUEST)

            order = create_order(
                user=request.user,
                tenant=request.tenant,
                address=address,
                description="Placed after successful mobile money payment",
            )
            order = transition_order_status(order=order, new_status=Order.Status.PAID, changed_by=request.user, note="Paid via mobile money")

            for cart_item in cart_items:
                variant = cart_item.variant.__class__.objects.select_for_update().get(id=cart_item.variant.id)
                quantity = cart_item.quantity
                if variant.stock_quantity < quantity:
                    return Response({"detail": f"Insufficient stock for {variant.product.title} ({variant.name})"}, status=status.HTTP_400_BAD_REQUEST)
                variant.stock_quantity -= quantity
                variant.save(update_fields=["stock_quantity"])
                add_order_item(order=order, variant=variant, quantity=quantity)

            order.recalculate_total_price()
            CartItem.objects.filter(id__in=[item.id for item in cart_items]).delete()
            payment.order = order
            payment.tenant = request.tenant
            payment.save(update_fields=["order", "tenant", "updated_at"])

            output = OrderReadSerializer(order, context={"request": request})
            return Response({"order": output.data, "payment_reference": payment.reference}, status=status.HTTP_201_CREATED)
