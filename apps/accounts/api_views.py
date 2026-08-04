from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .jwt_serializers import EmailTokenObtainPairSerializer
from .models import User
from .serializers import (
    MeSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    SignupSerializer,
)
from .tokens import email_verification_token


def _send_verification_email(user):
    """
    Send the email verification link. Uses fail_silently so that a broken
    SMTP configuration (e.g. missing API keys) never prevents signup from
    succeeding — the user can request a resend later.
    """
    try:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = email_verification_token.make_token(user)
        verify_url = f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"

        body = render_to_string(
            "accounts/email/verify_email.txt",
            {"user": user, "verify_url": verify_url, "site_name": "Kindred"},
        )
        send_mail(
            "Verify your Kindred account",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    except Exception:
        # Never let email failure break signup — log it and continue.
        import logging

        logging.getLogger(__name__).exception("Failed to send verification email to %s", user.email)


def _send_password_reset_email(user, token_generator):
    try:
        uid = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        reset_url = f"{settings.FRONTEND_URL}/reset-password?uid={uid}&token={token}"

        body = render_to_string(
            "accounts/email/password_reset.txt",
            {"user": user, "reset_url": reset_url},
        )
        send_mail(
            "Reset your Kindred password",
            body,
            settings.DEFAULT_FROM_EMAIL,
            [user.email],
            fail_silently=True,
        )
    except Exception:
        import logging

        logging.getLogger(__name__).exception("Failed to send password reset email to %s", user.email)


class SignupView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        _send_verification_email(user)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "user": MeSerializer(user).data,
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )