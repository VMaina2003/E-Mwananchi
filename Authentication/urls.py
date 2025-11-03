from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)
from .views import (
    RegisterView,
    VerifyEmailView,
    LoginView,
    RequestPasswordResetView,
    ResetPasswordView,
    CustomTokenVerifyView,
    ResendVerificationEmailView,
    LogoutView,
    CurrentUserView,
    GoogleAuthView,
    AppleAuthView,
    SocialAuthView,
)

urlpatterns = [
    # ==================== USER REGISTRATION & VERIFICATION ====================
    path("register/", RegisterView.as_view(), name="register"),
    path("verify-email/", VerifyEmailView.as_view(), name="verify-email"),
    path("resend-verification/", ResendVerificationEmailView.as_view(), name="resend-verification"),
    
    # ==================== AUTHENTICATION ROUTES ====================
    path("login/", LoginView.as_view(), name="login"),
    path("logout/", LogoutView.as_view(), name="logout"),
    
    # ==================== SOCIAL AUTHENTICATION ====================
    path("google/", GoogleAuthView.as_view(), name="google-auth"),
    path("apple/", AppleAuthView.as_view(), name="apple-auth"),
    path("social/", SocialAuthView.as_view(), name="social-auth"),
    
    # ==================== PASSWORD MANAGEMENT ====================
    path("request-password-reset/", RequestPasswordResetView.as_view(), name="request-password-reset"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),

    # ==================== JWT TOKEN MANAGEMENT ====================
    path("token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/verify/", CustomTokenVerifyView.as_view(), name="token_verify"),
    
    # ==================== USER PROFILE & DATA ====================
    path("me/", CurrentUserView.as_view(), name="current-user"),
]