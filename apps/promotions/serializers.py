from decimal import Decimal

from rest_framework import serializers

from .models import Coupon


class CouponSerializer(serializers.ModelSerializer):
    is_valid_now = serializers.ReadOnlyField()

    class Meta:
        model = Coupon
        fields = (
            "id",
            "code",
            "description",
            "discount_type",
            "value",
            "min_order_amount",
            "max_discount_amount",
            "usage_limit",
            "used_count",
            "starts_at",
            "ends_at",
            "is_active",
            "products",
            "categories",
            "is_valid_now",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "used_count", "created_at", "updated_at")

    def validate(self, attrs):
        starts_at = attrs.get("starts_at")
        ends_at = attrs.get("ends_at")
        discount_type = attrs.get("discount_type")
        value = attrs.get("value")

        if starts_at and ends_at and starts_at >= ends_at:
            raise serializers.ValidationError("ends_at must be later than starts_at.")

        if discount_type == Coupon.DiscountType.PERCENTAGE and value > Decimal("100.00"):
            raise serializers.ValidationError({"value": "Percentage discount cannot exceed 100."})

        return attrs


class CouponValidateSerializer(serializers.Serializer):
    code = serializers.CharField()
    amount = serializers.DecimalField(max_digits=12, decimal_places=2)

    def validate(self, attrs):
        from django.utils import timezone
        from .models import Coupon

        code = attrs["code"].upper()
        amount = attrs["amount"]

        tenant = getattr(self.context.get("request"), "tenant", None)
        queryset = Coupon.objects.all()
        if tenant is not None:
            queryset = queryset.filter(tenant=tenant)

        try:
            coupon = queryset.get(code=code)
        except Coupon.DoesNotExist:
            raise serializers.ValidationError({"code": "Invalid coupon code."})

        now = timezone.now()
        if not coupon.is_active or coupon.starts_at > now or coupon.ends_at < now:
            raise serializers.ValidationError({"code": "Coupon is not active."})

        if coupon.usage_limit and coupon.used_count >= coupon.usage_limit:
            raise serializers.ValidationError({"code": "Coupon usage limit reached."})

        if amount < coupon.min_order_amount:
            raise serializers.ValidationError({"amount": "Order amount does not meet coupon minimum."})

        attrs["coupon"] = coupon
        return attrs