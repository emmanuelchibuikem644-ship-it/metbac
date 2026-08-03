from rest_framework_simplejwt.views import TokenRefreshView

from django.urls import path

from . import api_views

app_name = "accounts"

urlpatterns = [
    path("signup/", api_views.SignupView.as_view(), name="signup"),
    path("login/", api_views.EmailTokenObtainPairView.as_view(), name="login"),
    path("login/refresh/", TokenRefreshView.as_view(), name="login_refresh"),
    path("logout/", api_views.LogoutView.as_view(), name="logout"),
    path("me/", api_views.MeView.as_view(), name="me"),
    path("verify-email/", api_views.VerifyEmailView.as_view(), name="verify_email"),
    path("verify-email/resend/", api_views.ResendVerificationView.as_view(), name="resend_verification"),
    path("password-reset/", api_views.PasswordResetRequestView.as_view(), name="password_reset"),
    path("password-reset/confirm/", api_views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
]
