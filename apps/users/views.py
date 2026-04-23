from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework import generics, permissions, status, viewsets
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.exceptions import Throttled, ValidationError
from rest_framework.response import Response
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.authentication import JWTAuthentication

from apps.tenants.models import TenantMembership
from apps.tenants.permissions import is_platform_admin, user_has_tenant_role
from rest_framework_simplejwt.tokens import RefreshToken
import logging

from .models import EmailOTP
from .serializers import (
    ChangePasswordSerializer,
    ForgotPasswordSerializer,
    GoogleLoginSerializer,
    LoginSerializer,
    LogoutSerializer,
    RegisterSerializer,
    ResetPasswordSerializer,
    SendEmailVerificationSerializer,
    UserSerializer,
    UpdateProfileSerializer,
    VerifyEmailSerializer,
)
from .services import (
    authenticate_with_google,
    ensure_resend_allowed,
    generate_tokens_for_user,
    get_latest_active_otp,
    issue_email_otp,
    send_password_reset_email,
    send_verification_email,
)

User = get_user_model()
logger = logging.getLogger(__name__)


class AuthAnonThrottle(AnonRateThrottle):
    scope = "auth_anon"


class AuthUserThrottle(UserRateThrottle):
    scope = "auth_user"


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def get_queryset(self):
        queryset = User.objects.prefetch_related("tenant_memberships__tenant").order_by("-created_at")
        if is_platform_admin(self.request.user):
            return queryset

        tenant = getattr(self.request, "tenant", None)
        if user_has_tenant_role(self.request.user, tenant, TenantMembership.Role.STAFF):
            return queryset.filter(
                tenant_memberships__tenant=tenant,
                tenant_memberships__is_active=True,
            ).distinct()

        return queryset.filter(pk=self.request.user.pk)


class RegisterView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthAnonThrottle]

    def post(self, request, *args, **kwargs):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = serializer.save()
        tokens = generate_tokens_for_user(user)

        _, raw_code = issue_email_otp(
            user=user,
            purpose=EmailOTP.Purpose.VERIFY_EMAIL,
        )
        send_verification_email(user=user, code=raw_code)

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens,
                "detail": "Registration successful. Verification code sent to email.",
            },
            status=status.HTTP_201_CREATED,
        )


class LoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthAnonThrottle]

    def post(self, request, *args, **kwargs):
        serializer = LoginSerializer(
            data=request.data,
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)

        user = serializer.validated_data["user"]
        tokens = generate_tokens_for_user(user)

        return Response(
            {
                "user": UserSerializer(user).data,
                "tokens": tokens,
            },
            status=status.HTTP_200_OK,
        )



class MeView(generics.RetrieveUpdateAPIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get_object(self):
        return self.request.user

    def get_serializer_class(self):
        if self.request.method in ["PATCH", "PUT"]:
            return UpdateProfileSerializer
        return UserSerializer

    def patch(self, request, *args, **kwargs):
        serializer = self.get_serializer(
            self.get_object(),
            data=request.data,
            partial=True,
        )
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        logger.info(
            "Updated profile user_id=%s request_id=%s",
            request.user.id,
            getattr(request, "id", ""),
        )

        return Response(UserSerializer(request.user).data)
    

class LogoutView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    throttle_classes = [AuthUserThrottle]

    def post(self, request, *args, **kwargs):
        serializer = LogoutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        refresh_token = serializer.validated_data["refresh"]

        try:
            token = RefreshToken(refresh_token)
            token.blacklist()
        except Exception as exc:
            raise ValidationError(
                {"refresh": "Invalid or expired refresh token."}
            ) from exc

        return Response(
            {"detail": "Logout successful."},
            status=status.HTTP_200_OK,
        )


class GoogleLoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthAnonThrottle]

    def post(self, request, *args, **kwargs):
        serializer = GoogleLoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        result = authenticate_with_google(
            access_token=serializer.validated_data["access_token"],
            request=request,
        )

        return Response(
            {
                "user": UserSerializer(result.user).data,
                "tokens": result.tokens,
            },
            status=status.HTTP_200_OK,
        )


class ForgotPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthAnonThrottle]

    def post(self, request, *args, **kwargs):
        serializer = ForgotPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        user = User.objects.filter(email__iexact=email, is_active=True).first()

        if user and ensure_resend_allowed(
            user=user,
            purpose=EmailOTP.Purpose.RESET_PASSWORD,
        ):
            _, raw_code = issue_email_otp(
                user=user,
                purpose=EmailOTP.Purpose.RESET_PASSWORD,
            )
            send_password_reset_email(user=user, code=raw_code)

        return Response(
            {"detail": "If an account exists with that email, a reset code has been sent."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [AuthAnonThrottle]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = ResetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        code = serializer.validated_data["code"]
        new_password = serializer.validated_data["password"]

        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not user:
            raise ValidationError({"detail": "Invalid or expired code."})

        otp = get_latest_active_otp(
            user=user,
            purpose=EmailOTP.Purpose.RESET_PASSWORD,
        )
        if not otp or otp.is_used() or otp.is_expired() or not otp.can_attempt():
            raise ValidationError({"detail": "Invalid or expired code."})

        otp.attempts += 1
        otp.save(update_fields=["attempts"])

        if not otp.verify_code(code):
            raise ValidationError({"detail": "Invalid or expired code."})

        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Password reset successful."},
            status=status.HTTP_200_OK,
        )


class ChangePasswordView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    throttle_classes = [AuthUserThrottle]

    def post(self, request, *args, **kwargs):
        serializer = ChangePasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        current_password = serializer.validated_data["current_password"]
        new_password = serializer.validated_data["new_password"]

        if not user.check_password(current_password):
            raise ValidationError({"current_password": ["Current password is incorrect."]})

        if current_password == new_password:
            raise ValidationError({"new_password": ["New password must be different from current password."]})

        user.set_password(new_password)
        user.save(update_fields=["password"])

        return Response(
            {"detail": "Password changed successfully."},
            status=status.HTTP_200_OK,
        )


class SendEmailVerificationView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    throttle_classes = [AuthUserThrottle]

    def post(self, request, *args, **kwargs):
        serializer = SendEmailVerificationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user

        if user.is_email_verified:
            return Response(
                {"detail": "Email already verified."},
                status=status.HTTP_200_OK,
            )

        if not ensure_resend_allowed(
            user=user,
            purpose=EmailOTP.Purpose.VERIFY_EMAIL,
        ):
            raise Throttled(detail="Please wait before requesting another code.")

        _, raw_code = issue_email_otp(
            user=user,
            purpose=EmailOTP.Purpose.VERIFY_EMAIL,
        )
        send_verification_email(user=user, code=raw_code)

        return Response(
            {"detail": "Verification code sent."},
            status=status.HTTP_200_OK,
        )


class VerifyEmailView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]
    throttle_classes = [AuthUserThrottle]

    @transaction.atomic
    def post(self, request, *args, **kwargs):
        serializer = VerifyEmailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user = request.user
        code = serializer.validated_data["code"]

        if user.is_email_verified:
            return Response(
                {"detail": "Email already verified."},
                status=status.HTTP_200_OK,
            )

        otp = get_latest_active_otp(
            user=user,
            purpose=EmailOTP.Purpose.VERIFY_EMAIL,
        )
        if not otp or otp.is_used() or otp.is_expired() or not otp.can_attempt():
            raise ValidationError({"detail": "Invalid or expired code."})

        otp.attempts += 1
        otp.save(update_fields=["attempts"])

        if not otp.verify_code(code):
            raise ValidationError({"detail": "Invalid or expired code."})

        otp.used_at = timezone.now()
        otp.save(update_fields=["used_at"])

        user.is_email_verified = True
        user.save(update_fields=["is_email_verified"])

        return Response(
            {
                "detail": "Email verified successfully.",
                "user": UserSerializer(user).data,
            },
            status=status.HTTP_200_OK,
        )

from apps.tenants.permissions import get_user_tenant_role

class CurrentTenantRoleView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        role = get_user_tenant_role(request.user, getattr(request, "tenant", None))
        return Response({"tenant": getattr(request.tenant, "slug", None), "role": role}, status=status.HTTP_200_OK)
