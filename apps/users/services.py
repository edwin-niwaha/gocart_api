from dataclasses import dataclass
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth import authenticate, get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

from .models import EmailOTP

User = get_user_model()

EMAIL_OTP_RESEND_COOLDOWN_SECONDS = 60
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


@dataclass
class AuthResult:
    user: Any
    tokens: dict[str, str]


def normalize_email(email: str) -> str:
    return User.objects.normalize_email(email).lower()  # type: ignore[attr-defined]


def generate_tokens_for_user(user) -> dict[str, str]:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@transaction.atomic
def register_user(*, email: str, username: str, password: str):
    email = normalize_email(email)

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "A user with this email already exists."})

    return User.objects.create_user(
        email=email,
        username=username,
        password=password,
    )


def authenticate_user(*, email: str, password: str, request=None) -> AuthResult:
    email = normalize_email(email)

    user = authenticate(
        request=request,
        username=email,
        password=password,
    )

    if not user:
        raise AuthenticationFailed("Invalid email or password.")

    if not user.is_active:
        raise AuthenticationFailed("This account is inactive.")

    return AuthResult(
        user=user,
        tokens=generate_tokens_for_user(user),
    )


def authenticate_with_google(*, access_token: str, request=None) -> AuthResult:
    try:
        response = requests.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    except requests.RequestException as exc:
        raise AuthenticationFailed("Unable to reach Google authentication service.") from exc

    if response.status_code != 200:
        raise AuthenticationFailed("Invalid Google access token.")

    data = response.json()

    email = data.get("email")
    email_verified = data.get("email_verified", False)
    first_name = data.get("given_name", "")
    last_name = data.get("family_name", "")
    picture = data.get("picture", "")

    if not email:
        raise AuthenticationFailed("Google account email not available.")

    if not email_verified:
        raise AuthenticationFailed("Google email is not verified.")

    email = normalize_email(email)
    user = User.objects.filter(email__iexact=email).first()

    if not user:
        base_username = email.split("@")[0]
        username = base_username
        counter = 1

        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1

        user = User.objects.create_user(
            email=email,
            username=username,
            password=None,
        )

    if not user.is_active:
        raise AuthenticationFailed("This account is inactive.")

    fields_to_update: list[str] = []

    if first_name and getattr(user, "first_name", "") != first_name:
        user.first_name = first_name
        fields_to_update.append("first_name")

    if last_name and getattr(user, "last_name", "") != last_name:
        user.last_name = last_name
        fields_to_update.append("last_name")

    if (
        picture
        and hasattr(user, "avatar")
        and user.avatar != picture
    ):
        user.avatar = picture
        fields_to_update.append("avatar")

    if hasattr(user, "is_email_verified") and not user.is_email_verified:
        user.is_email_verified = True
        fields_to_update.append("is_email_verified")

    if fields_to_update:
        if hasattr(user, "updated_at"):
            fields_to_update.append("updated_at")
        user.save(update_fields=fields_to_update)

    return AuthResult(
        user=user,
        tokens=generate_tokens_for_user(user),
    )


def send_plain_email(*, to_email: str, subject: str, message: str) -> None:
    send_mail(
        subject=subject,
        message=message,
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[to_email],
        fail_silently=False,
    )


def get_latest_active_otp(*, user, purpose: str):
    now = timezone.now()
    return (
        EmailOTP.objects.filter(
            user=user,
            purpose=purpose,
            used_at__isnull=True,
            expires_at__gt=now,
        )
        .order_by("-created_at")
        .first()
    )


def ensure_resend_allowed(*, user, purpose: str) -> bool:
    latest = (
        EmailOTP.objects.filter(user=user, purpose=purpose)
        .order_by("-created_at")
        .first()
    )
    if not latest:
        return True

    delta = (timezone.now() - latest.created_at).total_seconds()
    return delta >= EMAIL_OTP_RESEND_COOLDOWN_SECONDS


def issue_email_otp(*, user, purpose: str):
    otp, raw_code = EmailOTP.create_otp(
        user=user,
        email=user.email,
        purpose=purpose,
        ttl_minutes=10,
    )
    return otp, raw_code


def send_verification_email(*, user, code: str) -> None:
    send_plain_email(
        to_email=user.email,
        subject="GoCart email verification code",
        message=(
            f"Your GoCart email verification code is {code}. "
            "It expires in 10 minutes."
        ),
    )


def send_password_reset_email(*, user, code: str) -> None:
    send_plain_email(
        to_email=user.email,
        subject="GoCart password reset code",
        message=(
            f"Your GoCart password reset code is {code}. "
            "It expires in 10 minutes."
        ),
    )


@transaction.atomic
def claim_guest_session_data(*, user, guest_session_key: str | None) -> dict[str, int]:
    if not guest_session_key:
        return {
            "claimed_cart_items": 0,
            "merged_cart_items": 0,
            "claimed_orders": 0,
            "claimed_payments": 0,
        }

    from apps.cart.services import claim_guest_cart
    from apps.orders.models import Order
    from apps.payments.models import Payment

    timestamp = timezone.now()
    cart_result = claim_guest_cart(user=user, guest_session_key=guest_session_key)
    claimed_orders = Order.objects.filter(
        user__isnull=True,
        guest_session_key=guest_session_key,
    ).update(
        user=user,
        guest_session_key=None,
        updated_at=timestamp,
    )
    claimed_payments = Payment.objects.filter(
        user__isnull=True,
        guest_session_key=guest_session_key,
    ).update(
        user=user,
        guest_session_key=None,
        updated_at=timestamp,
    )
    return {
        "claimed_cart_items": cart_result["claimed_items"],
        "merged_cart_items": cart_result["merged_items"],
        "claimed_orders": claimed_orders,
        "claimed_payments": claimed_payments,
    }
