from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import timedelta
from decimal import Decimal
from unittest.mock import Mock

from apps.addresses.models import CustomerAddress
from apps.cart.models import Cart, CartItem
from apps.orders.models import Order
from apps.orders.tasks import (
    _run_email_task,
    send_admin_order_status_email_task,
    send_customer_order_status_email_task,
    send_new_order_admin_email_task,
    send_order_confirmation_email_task,
    send_order_push_notification_task,
)
from apps.payments.models import Payment
from apps.products.models import Category, Product, ProductVariant
from apps.promotions.models import Coupon
from apps.shipping.models import ShippingMethod
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


@override_settings(CELERY_TASK_ALWAYS_EAGER=True, CELERY_TASK_EAGER_PROPAGATES=True, ENABLE_EMAIL=False)
class OrderTenantCheckoutTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(email="buyer@example.com", username="buyer", password="secret123")
        self.client.force_authenticate(user=self.user)
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        self.category_a = Category.objects.create(tenant=self.tenant_a, name="Fruits", slug="fruits")
        self.category_b = Category.objects.create(tenant=self.tenant_b, name="Veg", slug="veg")
        self.product_a = Product.objects.create(tenant=self.tenant_a, category=self.category_a, title="Apple", slug="apple")
        self.product_b = Product.objects.create(tenant=self.tenant_b, category=self.category_b, title="Carrot", slug="carrot")
        self.variant_a = ProductVariant.objects.create(tenant=self.tenant_a, product=self.product_a, name="1kg", sku="A1", price="1000.00", stock_quantity=10)
        self.variant_b = ProductVariant.objects.create(tenant=self.tenant_b, product=self.product_b, name="1kg", sku="B1", price="2000.00", stock_quantity=10)
        self.address = CustomerAddress.objects.create(user=self.user, street_name="Plot 1", city="Kampala", region=CustomerAddress.Region.KAMPALA_AREA)
        self.cart = Cart.objects.create(user=self.user)

    def test_checkout_uses_active_tenant_items_only(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")
        CartItem.objects.create(cart=self.cart, variant=self.variant_b, quantity=1, unit_price="2000.00")

        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": self.address.id, "description": "checkout"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )
        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(slug=response.data["order"]["slug"])
        self.assertEqual(order.tenant, self.tenant_a)
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().variant, self.variant_a)

    def test_checkout_applies_coupon_and_shipping_to_order_payment_total(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")
        shipping_method = ShippingMethod.objects.create(
            name="Kampala delivery",
            fee="500.00",
            estimated_days=1,
            is_active=True,
        )
        coupon = Coupon.objects.create(
            tenant=self.tenant_a,
            code="SAVE300",
            discount_type=Coupon.DiscountType.FIXED,
            value="300.00",
            starts_at=timezone.now() - timedelta(days=1),
            ends_at=timezone.now() + timedelta(days=1),
            is_active=True,
        )

        response = self.client.post(
            "/api/v1/orders/checkout/",
            {
                "address_id": self.address.id,
                "shipping_method_id": shipping_method.id,
                "coupon_code": "save300",
                "payment_method": Payment.Provider.CASH,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(slug=response.data["order"]["slug"])
        payment = Payment.objects.get(order=order)
        coupon.refresh_from_db()

        self.assertEqual(order.total_price, 2200)
        self.assertEqual(payment.amount, order.total_price)
        self.assertEqual(coupon.used_count, 1)
        self.assertEqual(payment.provider_response["checkout_summary"]["items_subtotal"], "2000.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["discount"], "300.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["shipping"], "500.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["total"], "2200.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["coupon_code"], coupon.code)
        self.assertEqual(
            payment.provider_response["checkout_summary"]["shipping_method_id"],
            shipping_method.id,
        )

    def test_checkout_replay_after_cart_consumed_does_not_create_duplicate_order(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")

        first_response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": self.address.id, "description": "first checkout"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )
        second_response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": self.address.id, "description": "second checkout"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 400)
        self.assertEqual(Order.objects.count(), 1)
        self.variant_a.refresh_from_db()
        self.assertEqual(self.variant_a.stock_quantity, 8)

    def test_checkout_idempotency_replays_order_and_charges_shipping_once(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")
        variant_c = ProductVariant.objects.create(
            tenant=self.tenant_a,
            product=self.product_a,
            name="500g",
            sku="A2",
            price="1000.00",
            stock_quantity=10,
        )
        CartItem.objects.create(cart=self.cart, variant=variant_c, quantity=1, unit_price="1000.00")
        shipping_method = ShippingMethod.objects.create(
            name="Kampala express",
            fee="5000.00",
            estimated_days=1,
            is_active=True,
        )
        payload = {
            "address_id": self.address.id,
            "shipping_method_id": shipping_method.id,
            "payment_method": Payment.Provider.CASH,
        }
        headers = {
            "HTTP_X_TENANT_SLUG": self.tenant_a.slug,
            "HTTP_IDEMPOTENCY_KEY": "checkout-test-key-001",
        }

        first_response = self.client.post(
            "/api/v1/orders/checkout/",
            payload,
            format="json",
            **headers,
        )
        second_response = self.client.post(
            "/api/v1/orders/checkout/",
            payload,
            format="json",
            **headers,
        )

        self.assertEqual(first_response.status_code, 201)
        self.assertEqual(second_response.status_code, 200)
        self.assertEqual(first_response.data["order"]["slug"], second_response.data["order"]["slug"])
        self.assertEqual(Order.objects.count(), 1)
        self.assertEqual(Payment.objects.count(), 1)

        order = Order.objects.get(slug=first_response.data["order"]["slug"])
        payment = Payment.objects.get(order=order)

        self.assertEqual(order.items.count(), 2)
        self.assertEqual(order.total_price, Decimal("8000.00"))
        self.assertEqual(payment.amount, order.total_price)
        self.assertEqual(payment.provider_response["checkout_summary"]["items_subtotal"], "3000.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["shipping"], "5000.00")
        self.assertEqual(payment.provider_response["checkout_summary"]["total"], "8000.00")
        self.assertEqual(payment.provider_response["idempotency_key"], "checkout-test-key-001")

    def test_checkout_insufficient_stock_does_not_create_order_or_payment(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")
        ProductVariant.objects.filter(pk=self.variant_a.pk).update(stock_quantity=1)

        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": self.address.id, "description": "stock check"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Insufficient stock for Apple (1kg)")
        self.assertEqual(response.data["errors"], {})
        self.assertEqual(response.data["code"], "validation_error")
        self.assertFalse(Order.objects.exists())
        self.assertFalse(Payment.objects.exists())
        self.assertEqual(CartItem.objects.count(), 1)
        self.variant_a.refresh_from_db()
        self.assertEqual(self.variant_a.stock_quantity, 1)

    @override_settings(ENABLED_CHECKOUT_PAYMENT_METHODS=["CASH", "MTN"])
    def test_checkout_mtn_creates_awaiting_payment_without_provider_call(self):
        CartItem.objects.create(cart=self.cart, variant=self.variant_a, quantity=2, unit_price="1000.00")

        response = self.client.post(
            "/api/v1/orders/checkout/",
            {
                "address_id": self.address.id,
                "description": "mtn checkout",
                "payment_method": Payment.Provider.MTN,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(slug=response.data["order"]["slug"])
        payment = Payment.objects.get(order=order)
        self.assertEqual(order.status, Order.Status.AWAITING_PAYMENT)
        self.assertEqual(payment.provider, Payment.Provider.MTN)
        self.assertEqual(payment.status, Payment.Status.PROCESSING)
        self.assertEqual(payment.amount, order.total_price)

    def test_tenant_staff_can_checkout_own_cart(self):
        staff = User.objects.create_user(email="checkout-staff@example.com", username="checkoutstaff", password="secret123")
        TenantMembership.objects.create(tenant=self.tenant_a, user=staff, role=TenantMembership.Role.STAFF)
        staff_address = CustomerAddress.objects.create(
            user=staff,
            street_name="Plot 88",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        staff_cart = Cart.objects.create(user=staff)
        CartItem.objects.create(cart=staff_cart, variant=self.variant_a, quantity=1, unit_price="1000.00")

        self.client.force_authenticate(user=staff)
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": staff_address.id, "description": "seller buying for self"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 201)
        order = Order.objects.get(slug=response.data["order"]["slug"])
        self.assertEqual(order.user, staff)
        self.assertEqual(order.items.count(), 1)
        self.assertFalse(CartItem.objects.filter(cart=staff_cart).exists())

    def test_tenant_staff_cannot_checkout_with_customer_address(self):
        staff = User.objects.create_user(email="checkout-staff-2@example.com", username="checkoutstaff2", password="secret123")
        other_user = User.objects.create_user(email="other-buyer@example.com", username="otherbuyer", password="secret123")
        TenantMembership.objects.create(tenant=self.tenant_a, user=staff, role=TenantMembership.Role.STAFF)
        other_address = CustomerAddress.objects.create(
            user=other_user,
            street_name="Plot 99",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        staff_cart = Cart.objects.create(user=staff)
        CartItem.objects.create(cart=staff_cart, variant=self.variant_a, quantity=1, unit_price="1000.00")

        self.client.force_authenticate(user=staff)
        response = self.client.post(
            "/api/v1/orders/checkout/",
            {"address_id": other_address.id, "description": "invalid address"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.data["detail"], "Address not found.")
        self.assertEqual(response.data["code"], "validation_error")
        self.assertFalse(Order.objects.filter(user=staff).exists())


class OrderStaffVisibilityTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(email="buyer2@example.com", username="buyer2", password="secret123")
        self.staff = User.objects.create_user(email="staff@example.com", username="staff", password="secret123")
        self.tenant = Tenant.objects.create(name="Tenant Staff", slug="tenant-staff", is_active=True, is_default=True)
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)
        address = CustomerAddress.objects.create(user=self.customer, street_name="Plot 2", city="Kampala", region=CustomerAddress.Region.KAMPALA_AREA)
        self.order = Order.objects.create(user=self.customer, tenant=self.tenant, address=address, status=Order.Status.PENDING, slug="ord-staff")

    def test_staff_can_list_tenant_orders(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.get("/api/v1/orders/", HTTP_X_TENANT_SLUG=self.tenant.slug)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 1)


class OrderStatusTransitionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.customer = User.objects.create_user(email="buyer3@example.com", username="buyer3", password="secret123")
        self.staff = User.objects.create_user(email="staff3@example.com", username="staff3", password="secret123")
        self.tenant = Tenant.objects.create(name="Tenant Ops", slug="tenant-ops", is_active=True, is_default=True)
        TenantMembership.objects.create(tenant=self.tenant, user=self.staff, role=TenantMembership.Role.STAFF)
        address = CustomerAddress.objects.create(user=self.customer, street_name="Plot 3", city="Kampala", region=CustomerAddress.Region.KAMPALA_AREA)
        self.order = Order.objects.create(user=self.customer, tenant=self.tenant, address=address, status=Order.Status.PENDING, slug="ord-transition")

    def test_staff_can_transition_order_status(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            f"/api/v1/orders/{self.order.slug}/transition-status/",
            {"status": Order.Status.PROCESSING, "note": "Picked"},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 200)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, Order.Status.PROCESSING)
        self.assertEqual(self.order.status_events.count(), 1)

    def test_customer_cannot_transition_order_status(self):
        self.client.force_authenticate(user=self.customer)
        response = self.client.post(
            f"/api/v1/orders/{self.order.slug}/transition-status/",
            {"status": Order.Status.PROCESSING},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_transition_returns_specific_message(self):
        self.client.force_authenticate(user=self.staff)
        response = self.client.post(
            f"/api/v1/orders/{self.order.slug}/transition-status/",
            {"status": Order.Status.DELIVERED},
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertEqual(
            response.data["detail"],
            "Cannot transition order from PENDING to DELIVERED.",
        )
        self.assertEqual(response.data["code"], "validation_error")


class OrderTaskReliabilityTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(email="task-buyer@example.com", username="taskbuyer", password="secret123")
        self.tenant = Tenant.objects.create(name="Task Tenant", slug="order-task-tenant", is_active=True, is_default=True)
        self.address = CustomerAddress.objects.create(
            user=self.user,
            street_name="Plot 5",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        self.order = Order.objects.create(
            user=self.user,
            tenant=self.tenant,
            address=self.address,
            status=Order.Status.PENDING,
            slug="order-task-test",
        )

    def test_order_tasks_have_retry_policy(self):
        for task in (
            send_order_confirmation_email_task,
            send_new_order_admin_email_task,
            send_customer_order_status_email_task,
            send_admin_order_status_email_task,
            send_order_push_notification_task,
        ):
            self.assertEqual(task.autoretry_for, (Exception,))
            self.assertTrue(task.retry_backoff)
            self.assertTrue(task.retry_jitter)
            self.assertEqual(task.retry_backoff_max, 300)
            self.assertEqual(task.max_retries, 5)

    def test_missing_order_email_task_is_skipped_without_sender_call(self):
        sender = Mock()

        _run_email_task(
            order_id=999999,
            action_label="test order email",
            sender=sender,
        )

        sender.assert_not_called()

    def test_order_email_task_reraises_sender_failure_for_celery_retry(self):
        sender = Mock(side_effect=RuntimeError("smtp unavailable"))

        with self.assertRaises(RuntimeError):
            _run_email_task(
                order_id=self.order.id,
                action_label="test order email",
                sender=sender,
                recipient_getter=lambda order: order.user.email,
            )

        sender.assert_called_once_with(self.order)
