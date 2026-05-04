from django.contrib.auth import get_user_model
from rest_framework import serializers

from .models import Tenant, TenantBranding, TenantFeatureFlag, TenantMembership, TenantSettings
from .permissions import ROLE_ORDER

User = get_user_model()


class TenantBrandingSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantBranding
        fields = (
            "app_name",
            "logo_url",
            "primary_color",
            "secondary_color",
            "accent_color",
            "splash_image_url",
            "hero_title",
            "hero_subtitle",
        )


class TenantSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantSettings
        fields = (
            "order_notifications_enabled",
            "reviews_enabled",
            "coupons_enabled",
            "delivery_enabled",
            "wishlist_enabled",
            "support_chat_url",
            "website_url",
            "terms_url",
            "privacy_url",
            "maintenance_mode",
        )


class TenantFeatureFlagSerializer(serializers.ModelSerializer):
    class Meta:
        model = TenantFeatureFlag
        fields = ("id", "key", "enabled", "description", "created_at", "updated_at")


class TenantSerializer(serializers.ModelSerializer):
    branding = TenantBrandingSerializer(read_only=True)
    settings = TenantSettingsSerializer(read_only=True)
    feature_flags = TenantFeatureFlagSerializer(many=True, read_only=True)

    class Meta:
        model = Tenant
        fields = (
            "id",
            "name",
            "slug",
            "is_active",
            "support_email",
            "support_phone",
            "currency",
            "default_country",
            "timezone",
            "is_default",
            "branding",
            "settings",
            "feature_flags",
        )


class TenantMembershipSerializer(serializers.ModelSerializer):
    tenant = TenantSerializer(read_only=True)
    user = serializers.SerializerMethodField()
    user_id = serializers.IntegerField(read_only=True)
    tenant_name = serializers.CharField(source="tenant.name", read_only=True)
    tenant_slug = serializers.CharField(source="tenant.slug", read_only=True)
    email = serializers.EmailField(source="user.email", read_only=True)
    username = serializers.CharField(source="user.username", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_is_active = serializers.BooleanField(source="user.is_active", read_only=True)
    is_email_verified = serializers.BooleanField(source="user.is_email_verified", read_only=True)
    full_name = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = TenantMembership
        fields = (
            "id",
            "tenant",
            "tenant_name",
            "tenant_slug",
            "user",
            "user_id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "role",
            "is_active",
            "user_is_active",
            "is_email_verified",
            "status",
            "created_at",
            "updated_at",
        )

    def get_user(self, obj):
        return {
            "id": obj.user_id,
            "email": obj.user.email,
            "username": obj.user.username,
            "first_name": obj.user.first_name,
            "last_name": obj.user.last_name,
            "is_staff": obj.user.is_staff,
        }

    def get_full_name(self, obj):
        return obj.user.get_full_name().strip()

    def get_status(self, obj):
        if obj.is_active and obj.user.is_active:
            return "active"
        return "inactive"


class TenantMembershipWriteSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    user_id = serializers.IntegerField(required=False)
    username = serializers.CharField(required=False, allow_blank=False, max_length=150)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(required=False, write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=TenantMembership.Role.choices)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_email(self, value):
        return User.objects.normalize_email(value).lower()  # type: ignore[attr-defined]

    def validate_username(self, value):
        username = value.strip()
        if not username:
            raise serializers.ValidationError("Username cannot be blank.")
        return username

    def validate_first_name(self, value):
        return value.strip()

    def validate_last_name(self, value):
        return value.strip()

    def validate(self, attrs):
        if not attrs.get("email") and not attrs.get("user_id"):
            raise serializers.ValidationError({"detail": "Provide either email or user_id."})
        if attrs.get("email") and not attrs.get("user_id") and not attrs.get("password"):
            user_exists = User.objects.filter(email__iexact=attrs["email"]).exists()
            if not user_exists:
                raise serializers.ValidationError({"password": "Password is required when creating a new user."})
        username = attrs.get("username")
        if username and User.objects.filter(username__iexact=username).exists():
            email = attrs.get("email")
            if not email or not User.objects.filter(email__iexact=email, username__iexact=username).exists():
                raise serializers.ValidationError({"username": "This username is already taken."})
        return attrs

    def validate_role(self, value):
        actor = self.context["request"].user
        actor_role = self.context.get("actor_role")
        if actor_role and ROLE_ORDER.get(value, 0) >= ROLE_ORDER.get(actor_role, 0) and not getattr(actor, "is_superuser", False):
            raise serializers.ValidationError("You can only assign roles below your own.")
        return value


class TenantMembershipUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    username = serializers.CharField(required=False, allow_blank=False, max_length=150)
    first_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    last_name = serializers.CharField(required=False, allow_blank=True, max_length=150)
    password = serializers.CharField(required=False, write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=TenantMembership.Role.choices, required=False)
    is_active = serializers.BooleanField(required=False)
    user_is_active = serializers.BooleanField(required=False)

    def validate_email(self, value):
        membership = self.context["membership"]
        email = User.objects.normalize_email(value).lower()  # type: ignore[attr-defined]
        if User.objects.filter(email__iexact=email).exclude(pk=membership.user_id).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_username(self, value):
        membership = self.context["membership"]
        username = value.strip()
        if not username:
            raise serializers.ValidationError("Username cannot be blank.")
        if User.objects.filter(username__iexact=username).exclude(pk=membership.user_id).exists():
            raise serializers.ValidationError("This username is already taken.")
        return username

    def validate_first_name(self, value):
        return value.strip()

    def validate_last_name(self, value):
        return value.strip()

    def validate_role(self, value):
        actor = self.context["request"].user
        actor_role = self.context.get("actor_role")
        if actor_role and ROLE_ORDER.get(value, 0) >= ROLE_ORDER.get(actor_role, 0) and not getattr(actor, "is_superuser", False):
            raise serializers.ValidationError("You can only assign roles below your own.")
        return value


class TenantFeatureFlagWriteSerializer(serializers.Serializer):
    key = serializers.SlugField(max_length=100)
    enabled = serializers.BooleanField()
    description = serializers.CharField(required=False, allow_blank=True, max_length=255)
