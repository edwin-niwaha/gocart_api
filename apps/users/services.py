from dataclasses import dataclass

import requests
from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken

User = get_user_model()


@dataclass
class AuthResult:
    user: User  # type: ignore
    tokens: dict


def generate_tokens_for_user(user) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "refresh": str(refresh),
        "access": str(refresh.access_token),
    }


@transaction.atomic
def register_user(*, email: str, username: str, password: str):
    email = User.objects.normalize_email(email).lower()

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "A user with this email already exists."})

    return User.objects.create_user(
        email=email,
        username=username,
        password=password,
    )


def authenticate_user(*, email: str, password: str, request=None) -> AuthResult:
    email = User.objects.normalize_email(email).lower()

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
    response = requests.get(
        "https://www.googleapis.com/oauth2/v3/userinfo",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=10,
    )

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

    email = User.objects.normalize_email(email).lower()

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

    fields_to_update = []

    if first_name and user.first_name != first_name: # type: ignore
        user.first_name = first_name
        fields_to_update.append("first_name")

    if last_name and user.last_name != last_name:
        user.last_name = last_name
        fields_to_update.append("last_name")

    if picture and hasattr(user, "profile_picture_url") and user.profile_picture_url != picture:
        user.profile_picture_url = picture
        fields_to_update.append("profile_picture_url")

    if fields_to_update:
        if hasattr(user, "updated_at"):
            fields_to_update.append("updated_at")
        user.save(update_fields=fields_to_update)

    return AuthResult(
        user=user,
        tokens=generate_tokens_for_user(user),
    )