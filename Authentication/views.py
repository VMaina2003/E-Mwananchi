from django.contrib.auth import authenticate, get_user_model
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
#   REGISTER VIEW (Updated)
# ============================================================
from smtplib import SMTPException, SMTPRecipientsRefused

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        try:
            email_sent = send_verification_email(user)
            if email_sent:
                return Response(
                    {"message": "Account created. Please check your email to verify your account."},
                    status=status.HTTP_201_CREATED,
                )
            else:
                user.delete()
                return Response(
                    {"email": "Verification email could not be sent. Please try again later."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except (SMTPException, SMTPRecipientsRefused) as e:
            print(f" Email sending failed: {e}")
            user.delete()
            return Response(
                {"email": "Verification email could not be sent. Please try again later."},
                status=status.HTTP_400_BAD_REQUEST,
            )




# ============================================================
#   EMAIL VERIFICATION VIEW
# ============================================================
class VerifyEmailView(APIView):
    """Verify a user's email through a token link."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.GET.get("token")
        if not token:
            return Response({"error": "Token is missing."}, status=status.HTTP_400_BAD_REQUEST)

        user = verify_email_token(token)
        if not user:
            return Response({"error": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        if user.verified:
            return Response({"message": "Email already verified."}, status=status.HTTP_200_OK)

        user.verified = True
        user.is_active = True
        user.save(update_fields=["verified", "is_active"])
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

        if not user:
            return Response({"error": "Invalid email or password."}, status=status.HTTP_401_UNAUTHORIZED)

        if not user.verified or not user.is_active:
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
            },
            status=status.HTTP_200_OK,
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
            pass  # Prevent leaking valid/invalid emails

        return Response(
            {"message": "If this email exists, a password reset link has been sent."},
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
        user.save(update_fields=["password"])
        return Response({"message": "Password reset successfully."}, status=status.HTTP_200_OK)


# ============================================================
#   TOKEN VERIFY VIEW
# ============================================================
class CustomTokenVerifyView(TokenVerifyView):
    """Verifies JWT token validity."""

    permission_classes = [permissions.AllowAny]
