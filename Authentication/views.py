from django.contrib.auth import authenticate, get_user_model
from django.shortcuts import get_object_or_404
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenVerifyView

from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
)
from .utils import (
    verify_email_token,
    send_verification_email,
    send_password_reset_email,
    verify_password_reset_token,
)

User = get_user_model()


# ============================================================
#   REGISTER VIEW
# ============================================================

class RegisterView(generics.CreateAPIView):
    """Register a new citizen user and send a verification email."""

    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def perform_create(self, serializer):
        user = serializer.save()
        send_verification_email(user)
        return user

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = self.perform_create(serializer)
        return Response(
            {"message": "Account created successfully. Check your email for verification."},
            status=status.HTTP_201_CREATED,
        )


# ============================================================
#   EMAIL VERIFICATION VIEW
# ============================================================

class VerifyEmailView(APIView):
    """Verifies a user's email through token link."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.GET.get("token", None)
        if not token:
            return Response({"error": "Token is missing."}, status=status.HTTP_400_BAD_REQUEST)

        user = verify_email_token(token)
        if not user:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        user.verified = True
        user.is_active = True
        user.save()
        return Response({"message": "Email verified successfully. You can now log in."})


# ============================================================
#   LOGIN VIEW
# ============================================================

class LoginView(APIView):
    """Authenticate user and return JWT tokens if verified."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"]
        password = serializer.validated_data["password"]

        user = authenticate(request, email=email, password=password)

        if user is None:
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.verified:
            return Response({"error": "Please verify your email first."}, status=status.HTTP_403_FORBIDDEN)

        refresh = RefreshToken.for_user(user)
        return Response(
            {
                "refresh": str(refresh),
                "access": str(refresh.access_token),
                "user": {
                    "id": str(user.id),
                    "email": user.email,
                    "full_name": user.get_full_name(),
                    "role": user.role,
                },
            }
        )


# ============================================================
#   REQUEST PASSWORD RESET VIEW
# ============================================================

class RequestPasswordResetView(APIView):
    """Send password reset link to user's email."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"]

        try:
            user = User.objects.get(email=email)
            send_password_reset_email(user)
        except User.DoesNotExist:
            pass  # Avoid leaking user existence

        return Response(
            {"message": "If this email exists, a reset link has been sent."},
            status=status.HTTP_200_OK,
        )


# ============================================================
#   PASSWORD RESET CONFIRM VIEW
# ============================================================

class ResetPasswordView(APIView):
    """Confirm password reset using token."""

    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = PasswordResetConfirmSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]
        new_password = serializer.validated_data["new_password"]

        user = verify_password_reset_token(token)
        if not user:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(new_password)
        user.save()
        return Response({"message": "Password reset successfully."})


# ============================================================
#   TOKEN VERIFY VIEW (for testing JWT)
# ============================================================

class CustomTokenVerifyView(TokenVerifyView):
    """Verifies JWT token validity."""
    permission_classes = [permissions.AllowAny]
