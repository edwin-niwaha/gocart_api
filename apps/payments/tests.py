from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch
from rest_framework.test import APIClient

from apps.addresses.models import CustomerAddress
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
from apps.payments.models import Payment
from apps.products.models import Category, Product, ProductVariant
from apps.promotions.models import Coupon
from apps.shipping.models import ShippingMethod
from apps.tenants.models import Tenant

User = get_user_model()


class PaymentFinalizeSafetyTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="pay@example.com", username="payer", password="pass123456")
        self.client.force_authenticate(user=self.user)
        self.tenant = Tenant.objects.create(name="Payments Tenant", slug="payments-tenant", is_active=True)
        self.category = Category.objects.create(tenant=self.tenant, name="Food", slug="food")
        self.product = Product.objects.create(tenant=self.tenant, category=self.category, title="Beans", slug="beans")
        self.variant = ProductVariant.objects.create(
            tenant=self.tenant,
            product=self.product,
            name="1kg",
            sku="beans-1kg",
            price="1000.00",
            stock_quantity=10,
        )
        self.address = CustomerAddress.objects.create(
            user=self.user,
            street_name="Plot 9",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        self.cart = Cart.objects.create(user=self.user)

    def create_discount_and_shipping(self):
        shipping_method = ShippingMethod.objects.create(
            name="Kampala delivery",
            fee="500.00",
            estimated_days=1,
            is_active=True,
        )
        coupon = Coupon.objects.create(
            tenant=self.tenant,
            code="SAVE300",
            discount_type=Coupon.DiscountType.FIXED,
            value="300.00",
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )
        return coupon, shipping_method

    @override_settings(
        ENABLE_MOMO=True,
        SUBSCRIPTION_KEY="test-subscription",
        MOMO_API_USER="test-user",
        MOMO_API_KEY="test-key",
        MOMO_BASE_URL="https://momo.example.test",
        MOMO_CURRENCY=Payment.Currency.UGX,
    )
    @patch("apps.payments.services.request_to_pay")
    def test_mtn_initiation_uses_coupon_and_shipping_total(self, request_to_pay):
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        coupon, shipping_method = self.create_discount_and_shipping()
        request_to_pay.return_value = {
            "reference_id": "mtn-reference",
            "status_code": 202,
            "data": {},
        }

        response = self.client.post(
            "/api/v1/payments/mtn/initiate/",
            {
                "address_id": self.address.id,
                "phone_number": "0772123456",
                "shipping_method_id": shipping_method.id,
                "coupon_code": "save300",
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 201)
        payment = Payment.objects.get(reference=response.data["reference"])
        coupon.refresh_from_db()

        self.assertEqual(payment.amount, Decimal("2200.00"))
        self.assertEqual(coupon.used_count, 0)
        self.assertEqual(payment.provider_response["cart_total"], "2000.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["discount"], "300.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["shipping"], "500.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["total"], "2200.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["coupon_code"], coupon.code)
        self.assertEqual(
            payment.provider_response["checkout_summary"]["shipping_method_id"],
            shipping_method.id,
        )
        request_to_pay.assert_called_once()
        self.assertEqual(request_to_pay.call_args.kwargs["amount"], Decimal("2200.00"))

    @override_settings(
        ENABLE_MOMO=True,
        SUBSCRIPTION_KEY="test-subscription",
        MOMO_API_USER="test-user",
        MOMO_API_KEY="test-key",
        MOMO_BASE_URL="https://momo.example.test",
        MOMO_CURRENCY=Payment.Currency.UGX,
    )
    @patch("apps.payments.services.request_to_pay")
    def test_mtn_initiation_idempotency_replays_existing_payment(self, request_to_pay):
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        request_to_pay.return_value = {
            "reference_id": "mtn-reference",
            "status_code": 202,
            "data": {},
        }
        payload = {
            "address_id": self.address.id,
            "phone_number": "0772123456",
        }
        headers = {
            "HTTP_X_TENANT_SLUG": self.tenant.slug,
            "HTTP_IDEMPOTENCY_KEY": "payment-initiate-key-001",
        }

        first_response = self.client.post(
            "/api/v1/payments/mtn/initiate/",
            payload,
            format="json",
            **headers,
        )
        second_response = self.client.post(
            "/api/v1/payments/mtn/initiate/",
            payload,
            format="json",
            **headers,
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.data["reference"], second_response.data["reference"])
        self.assertEqual(Payment.objects.count(), 1)
        request_to_pay.assert_called_once()

        payment = Payment.objects.get(reference=first_response.data["reference"])
        self.assertEqual(payment.provider_response["idempotency_key"], "payment-initiate-key-001")

    def test_finalize_paid_payment_applies_stored_coupon_and_shipping_total(self):
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        coupon, shipping_method = self.create_discount_and_shipping()
        payment = Payment.objects.create(
            tenant=self.tenant,
            user=self.user,
            provider=Payment.Provider.MTN,
            status=Payment.Status.PAID,
            amount="2200.00",
            currency=Payment.Currency.UGX,
            provider_response={
                "address_id": self.address.id,
                "cart_snapshot": [
                    {
                        "variant_id": self.variant.id,
                        "quantity": 2,
                        "unit_price": "1000.00",
                    }
                ],
                "cart_total": "2000.00",
                "checkout_summary": {
                    "items_subtotal": "2000.00",
                    "discount": "300.00",
                    "shipping": "500.00",
                    "total": "2200.00",
                    "coupon_id": coupon.id,
                    "coupon_code": coupon.code,
                    "shipping_method_id": shipping_method.id,
                },
            },
        )

        response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(slug=response.data["order"]["slug"])
        payment.refresh_from_db()
        coupon.refresh_from_db()
        self.variant.refresh_from_db()

        self.assertEqual(order.total_price, Decimal("2200.00"))
        self.assertEqual(payment.amount, order.total_price)
        self.assertEqual(payment.order, order)
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(self.variant.stock_quantity, 8)

    def test_finalize_paid_order_rejects_changed_cart_amount(self):
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        payment = Payment.objects.create(
            tenant=self.tenant,
            user=self.user,
            provider=Payment.Provider.MTN,
            status=Payment.Status.PAID,
            amount="1000.00",
            currency=Payment.Currency.UGX,
            provider_response={
                "address_id": self.address.id,
                "cart_snapshot": [
                    {
                        "variant_id": self.variant.id,
                        "quantity": 1,
                        "unit_price": "1000.00",
                    }
                ],
            },
        )

        response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)

    def test_finalize_paid_order_rejects_wrong_tenant(self):
        other_tenant = Tenant.objects.create(name="Other Payments Tenant", slug="other-payments-tenant", is_active=True)
        payment = Payment.objects.create(
            tenant=other_tenant,
            user=self.user,
            provider=Payment.Provider.MTN,
            status=Payment.Status.PAID,
            amount="1000.00",
            currency=Payment.Currency.UGX,
            provider_response={"address_id": self.address.id},
        )

        response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.data["detail"], "Payment not found.")
        self.assertEqual(response.data["errors"], {})
        self.assertEqual(response.data["code"], "not_found")
        self.assertEqual(Order.objects.count(), 0)

    def test_finalize_paid_order_with_insufficient_stock_does_not_create_order(self):
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        payment = Payment.objects.create(
            tenant=self.tenant,
            user=self.user,
            provider=Payment.Provider.MTN,
            status=Payment.Status.PAID,
            amount="2000.00",
            currency=Payment.Currency.UGX,
            provider_response={
                "address_id": self.address.id,
                "cart_snapshot": [
                    {
                        "variant_id": self.variant.id,
                        "quantity": 2,
                        "unit_price": "1000.00",
                    }
                ],
            },
        )
        ProductVariant.objects.filter(pk=self.variant.pk).update(stock_quantity=1)

        response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(Order.objects.count(), 0)
        payment.refresh_from_db()
        self.assertIsNone(payment.order)
        self.assertEqual(CartItem.objects.count(), 1)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 1)

    def test_finalize_paid_payment_returns_existing_advanced_order(self):
        order = Order.objects.create(
            tenant=self.tenant,
            user=self.user,
            address=self.address,
            status=Order.Status.SHIPPED,
            slug="paid-existing-order",
            total_price="1000.00",
        )
        payment = Payment.objects.create(
            tenant=self.tenant,
            user=self.user,
            order=order,
            provider=Payment.Provider.MTN,
            status=Payment.Status.PAID,
            amount="1000.00",
            currency=Payment.Currency.UGX,
            provider_response={"address_id": self.address.id},
        )

        response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(response.data["order"]["slug"], order.slug)

    def test_finalize_paid_payment_is_replay_safe_after_order_created(self):
        CartItem.objects.create(
            cart=self.cart,
            variant=self.variant,
            quantity=2,
            unit_price="1000.00",
        )
        payment = Payment.objects.create(
            tenant=self.tenant,
            user=self.user,
            provider=Payment.Provider.MTN,
            status=Payment.Status.PAID,
            amount="2000.00",
            currency=Payment.Currency.UGX,
            provider_response={
                "address_id": self.address.id,
                "cart_snapshot": [
                    {
                        "variant_id": self.variant.id,
                        "quantity": 2,
                        "unit_price": "1000.00",
                    }
                ],
            },
        )

        first_response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        second_response = self.client.post(
            f"/api/v1/payments/{payment.reference}/finalize-order/",
            {},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(first_response.data["order"]["slug"], second_response.data["order"]["slug"])
        self.assertEqual(CartItem.objects.count(), 0)
        self.variant.refresh_from_db()
        self.assertEqual(self.variant.stock_quantity, 8)
