from django.contrib.auth import authenticate, get_user_model, password_validation
from django.db import transaction
from rest_framework import serializers

from apps.tenants.serializers import TenantMembershipSerializer

User = get_user_model()


def normalize_email(value: str) -> str:
    return User.objects.normalize_email(value).lower()  # type: ignore[attr-defined]


class UserSerializer(serializers.ModelSerializer):
    avatar_url = serializers.SerializerMethodField()
    tenant_memberships = TenantMembershipSerializer(many=True, read_only=True)
    active_tenant_slug = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "avatar_url",
            "user_type",
            "is_active",
            "is_email_verified",
            "active_tenant_slug",
            "tenant_memberships",
            "created_at",
        )
        read_only_fields = (
            "id",
            "email",
            "user_type",
            "is_active",
            "is_email_verified",
            "active_tenant_slug",
            "tenant_memberships",
            "created_at",
            "avatar_url",
            "active_tenant_slug",
            "tenant_memberships",
        )

    def get_active_tenant_slug(self, obj):
        tenant = getattr(obj, "active_tenant", None)
        return tenant.slug if tenant else None

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        try:
            return obj.avatar.url
        except Exception:
            return None


class UpdateProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "username",
            "first_name",
            "last_name",
            "avatar",
        )

    def validate_username(self, value):
        user = self.instance
        qs = User.objects.filter(username__iexact=value).exclude(pk=user.pk)
        if qs.exists():
            raise serializers.ValidationError("This username is already taken.")
        return value


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField()
    username = serializers.CharField(max_length=150, trim_whitespace=True)
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    class Meta:
        model = User
        fields = (
            "email",
            "username",
            "password",
            "password_confirm",
        )

    def validate_email(self, value: str) -> str:
        email = normalize_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return email

    def validate_username(self, value: str) -> str:
        username = value.strip()
        if not username:
            raise serializers.ValidationError("Username is required.")
        return username

    def validate(self, attrs):
        password = attrs.get("password")
        password_confirm = attrs.pop("password_confirm", None)

        if password != password_confirm:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        password_validation.validate_password(password)
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        return User.objects.create_user(**validated_data)  # type: ignore[attr-defined]


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)

    default_error_messages = {
        "missing_credentials": "Email and password are required.",
        "invalid_credentials": "Invalid email or password.",
        "inactive_account": "This account is inactive.",
    }

    def validate_email(self, value: str) -> str:
        return normalize_email(value)

    def validate(self, attrs):
        email = attrs.get("email", "")
        password = attrs.get("password")

        if not email or not password:
            raise serializers.ValidationError(
                {"detail": self.error_messages["missing_credentials"]}
            )

        user = authenticate(
            request=self.context.get("request"),
            username=email,
            password=password,
        )

        if not user:
            raise serializers.ValidationError(
                {"detail": self.error_messages["invalid_credentials"]}
            )

        if not user.is_active:
            raise serializers.ValidationError(
                {"detail": self.error_messages["inactive_account"]}
            )

        attrs["user"] = user
        return attrs


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField(trim_whitespace=True)

    def validate_refresh(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Refresh token is required.")
        return value

    
class GoogleLoginSerializer(serializers.Serializer):
    access_token = serializers.CharField(trim_whitespace=True)

    def validate_access_token(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Access token is required.")
        return value


class ForgotPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value: str) -> str:
        return normalize_email(value)


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6, min_length=6, trim_whitespace=True)
    password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    def validate_email(self, value: str) -> str:
        return normalize_email(value)

    def validate_code(self, value: str) -> str:
        code = value.strip()
        if not code.isdigit():
            raise serializers.ValidationError("Code must contain only digits.")
        return code

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError(
                {"password_confirm": "Passwords do not match."}
            )

        password_validation.validate_password(attrs["password"])
        return attrs


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True, trim_whitespace=False)
    new_password = serializers.CharField(write_only=True, min_length=8, trim_whitespace=False)
    new_password_confirm = serializers.CharField(
        write_only=True,
        min_length=8,
        trim_whitespace=False,
    )

    def validate(self, attrs):
        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError(
                {"new_password_confirm": "Passwords do not match."}
            )

        password_validation.validate_password(attrs["new_password"])
        return attrs


class SendEmailVerificationSerializer(serializers.Serializer):
    """
    Empty request body serializer kept intentionally for explicit validation.
    """
    pass


class VerifyEmailSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=6, min_length=6, trim_whitespace=True)

    def validate_code(self, value: str) -> str:
        code = value.strip()
        if not code.isdigit():
            raise serializers.ValidationError("Code must contain only digits.")
        return code