from dataclasses import dataclass

from django.contrib.auth import authenticate, get_user_model
from django.db import transaction
from rest_framework.exceptions import AuthenticationFailed, ValidationError
from rest_framework_simplejwt.tokens import RefreshToken
from social_core.exceptions import AuthException
from social_django.utils import load_backend, load_strategy

User = get_user_model()


@dataclass
class AuthResult:
    user: User # type: ignore
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
    strategy = load_strategy(request)
    backend = load_backend(
        strategy=strategy,
        name="google-oauth2",
        redirect_uri=None,
    )

    try:
        user = backend.do_auth(access_token)
    except AuthException as exc:
        raise AuthenticationFailed("Google authentication failed.") from exc

    if not user:
        raise AuthenticationFailed("Google authentication failed.")

    social_auth = user.social_auth.filter(provider="google-oauth2").first()
    if social_auth:
        picture = social_auth.extra_data.get("picture")
        if picture and user.profile_picture_url != picture:
            user.profile_picture_url = picture
            user.save(update_fields=["profile_picture_url", "updated_at"])

    return AuthResult(
        user=user,
        tokens=generate_tokens_for_user(user),
    )