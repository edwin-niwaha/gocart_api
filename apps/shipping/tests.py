from django.contrib.auth import get_user_model
from django.test import TestCase
from decimal import Decimal
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.addresses.models import CustomerAddress
from apps.orders.models import Order
from apps.shipping.models import DeliveryRate, PickupStation, Shipment, ShippingMethod
from apps.shipping.services import get_checkout_shipping_fee, resolve_checkout_delivery_rate
from apps.tenants.models import Tenant, TenantMembership

User = get_user_model()


class ShipmentPermissionTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.tenant_a = Tenant.objects.create(name="Tenant A", slug="tenant-a", is_active=True, is_default=True)
        self.tenant_b = Tenant.objects.create(name="Tenant B", slug="tenant-b", is_active=True)
        self.staff_a = User.objects.create_user(email="ship-staff@example.com", username="shipstaff", password="pass123456")
        self.staff_a.is_staff = True
        self.staff_a.save(update_fields=["is_staff"])
        TenantMembership.objects.create(tenant=self.tenant_a, user=self.staff_a, role=TenantMembership.Role.STAFF)
        self.customer_b = User.objects.create_user(email="ship-buyer-b@example.com", username="shipbuyerb", password="pass123456")
        self.address_b = CustomerAddress.objects.create(
            user=self.customer_b,
            street_name="Plot B",
            city="Kampala",
            region=CustomerAddress.Region.KAMPALA_AREA,
        )
        self.order_b = Order.objects.create(
            user=self.customer_b,
            tenant=self.tenant_b,
            address=self.address_b,
            status=Order.Status.PAID,
            slug="tenant-b-order",
        )
        self.shipping_method = ShippingMethod.objects.create(
            name="Door delivery",
            fee="5000.00",
            estimated_days=2,
            is_active=True,
        )

    def test_tenant_staff_cannot_list_other_tenant_shipments(self):
        Shipment.objects.create(
            order=self.order_b,
            address=self.address_b,
            shipping_method=self.shipping_method,
            shipping_fee=self.shipping_method.fee,
        )
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.get("/api/v1/shipments/", HTTP_X_TENANT_SLUG=self.tenant_a.slug)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["count"], 0)

    def test_tenant_staff_cannot_create_shipment_for_other_tenant_order(self):
        self.client.force_authenticate(user=self.staff_a)

        response = self.client.post(
            "/api/v1/shipments/",
            {
                "order": self.order_b.id,
                "address": self.address_b.id,
                "shipping_method": self.shipping_method.id,
            },
            format="json",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(Shipment.objects.exists())

    def test_pickup_station_list_is_scoped_to_active_tenant(self):
        tenant_station = PickupStation.objects.create(
            tenant=self.tenant_a,
            name="Wandegeya Pickup",
            city="Kampala",
            area="Wandegeya",
            address="Stage 1",
            is_active=True,
        )
        global_station = PickupStation.objects.create(
            name="City Center Pickup",
            city="Kampala",
            area="Central",
            address="Main Street",
            is_active=True,
        )
        PickupStation.objects.create(
            tenant=self.tenant_b,
            name="Other Tenant Pickup",
            city="Kampala",
            area="Nakawa",
            address="Plot 5",
            is_active=True,
        )

        response = self.client.get(
            "/api/v1/pickup-stations/",
            HTTP_X_TENANT_SLUG=self.tenant_a.slug,
        )

        self.assertEqual(response.status_code, 200)
        returned_ids = {item["id"] for item in response.data["results"]}
        self.assertEqual(response.data["count"], 2)
        self.assertEqual(returned_ids, {tenant_station.id, global_station.id})


class DeliveryRatePricingTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(
            name="Delivery Rate Tenant",
            slug="delivery-rate-tenant",
            is_active=True,
            is_default=True,
        )

    def test_delivery_rate_resolution_prefers_area_then_city_then_region(self):
        region_rate = DeliveryRate.objects.create(
            tenant=self.tenant,
            region=CustomerAddress.Region.KAMPALA_AREA,
            city="",
            area="",
            fee="3000.00",
            estimated_days=4,
            is_active=True,
        )
        city_rate = DeliveryRate.objects.create(
            tenant=self.tenant,
            region=CustomerAddress.Region.KAMPALA_AREA,
            city="Kampala",
            area="",
            fee="2000.00",
            estimated_days=2,
            is_active=True,
        )
        area_rate = DeliveryRate.objects.create(
            tenant=self.tenant,
            region=CustomerAddress.Region.KAMPALA_AREA,
            city="Kampala",
            area="Ntinda",
            fee="1000.00",
            estimated_days=1,
            is_active=True,
        )

        self.assertEqual(
            resolve_checkout_delivery_rate(
                tenant=self.tenant,
                delivery_option=Order.DeliveryOption.HOME_DELIVERY,
                address_region=CustomerAddress.Region.KAMPALA_AREA,
                address_city="Kampala",
                address_area="Ntinda",
            ).id,
            area_rate.id,
        )
        self.assertEqual(
            resolve_checkout_delivery_rate(
                tenant=self.tenant,
                delivery_option=Order.DeliveryOption.HOME_DELIVERY,
                address_region=CustomerAddress.Region.KAMPALA_AREA,
                address_city="Kampala",
                address_area="Bukoto",
            ).id,
            city_rate.id,
        )
        self.assertEqual(
            resolve_checkout_delivery_rate(
                tenant=self.tenant,
                delivery_option=Order.DeliveryOption.HOME_DELIVERY,
                address_region=CustomerAddress.Region.KAMPALA_AREA,
                address_city="Mukono",
                address_area="",
            ).id,
            region_rate.id,
        )

    def test_delivery_rate_resolution_falls_back_to_broad_tenant_rate(self):
        broad_rate = DeliveryRate.objects.create(
            tenant=self.tenant,
            region=CustomerAddress.Region.CENTRAL_REGION,
            city="",
            area="",
            fee="7000.00",
            estimated_days=3,
            is_active=True,
        )

        rate = resolve_checkout_delivery_rate(
            tenant=self.tenant,
            delivery_option=Order.DeliveryOption.HOME_DELIVERY,
            address_region=CustomerAddress.Region.WESTERN_REGION,
            address_city="Mbarara",
            address_area="Kakoba",
        )

        self.assertEqual(rate, broad_rate)
        self.assertEqual(
            get_checkout_shipping_fee(
                tenant=self.tenant,
                delivery_option=Order.DeliveryOption.HOME_DELIVERY,
                address_region=CustomerAddress.Region.WESTERN_REGION,
                address_city="Mbarara",
                address_area="Kakoba",
            ),
            Decimal("7000.00"),
        )

    def test_home_delivery_fee_requires_any_active_rate(self):
        with self.assertRaisesMessage(
            ValidationError,
            "Delivery is not available for this location.",
        ):
            get_checkout_shipping_fee(
                tenant=self.tenant,
                delivery_option=Order.DeliveryOption.HOME_DELIVERY,
                address_region=CustomerAddress.Region.KAMPALA_AREA,
                address_city="Kampala",
                address_area="Ntinda",
            )
