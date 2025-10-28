from django.contrib.auth import authenticate, get_user_model
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenVerifyView

from smtplib import SMTPException, SMTPRecipientsRefused # Kept import for clarity

# Import your serializers and utils
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
#   REGISTER VIEW
# ============================================================
class RegisterView(generics.CreateAPIView):
    """
    Handles user registration and sends a verification email.
    """
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()

        try:
            # Attempt to send the verification email
            email_sent = send_verification_email(user)

            if email_sent:
                return Response(
                    {"message": "Account created. Please check your email to verify your account."},
                    status=status.HTTP_201_CREATED,
                )
            else:
                # If send_mail returns False but no exception was raised
                # This could happen if an internal logic error prevents sending
                user.delete()
                return Response(
                    {"detail": "Verification email could not be sent. Please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE, # Use 503 for service issues
                )
                
        except (SMTPException, SMTPRecipientsRefused) as e:
            # Handle rate limiting (450 4.2.1) and other SMTP errors gracefully
            print(f" Email sending failed: {e}")
            user.delete() # Ensure the user is not left in an unverified state
            return Response(
                {"detail": "Verification email service is temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            # Catch any other unexpected errors during the email process
            print(f" Unexpected error during email sending: {e}")
            user.delete()
            return Response(
                {"detail": "An unexpected error occurred during registration. Please contact support."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


# ------------------------------------------------------------

# ============================================================
#   EMAIL VERIFICATION VIEW
# ============================================================
class VerifyEmailView(APIView):
    """Verify a user's email through a token link."""

    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.GET.get("token")
        if not token:
            return Response({"detail": "Verification token is missing."}, status=status.HTTP_400_BAD_REQUEST)

        user = verify_email_token(token)
        if not user:
            return Response({"detail": "Invalid or expired token."}, status=status.HTTP_400_BAD_REQUEST)

        if user.verified:
            return Response({"detail": "Email already verified."}, status=status.HTTP_200_OK)

        # Use bulk update for atomicity and simplicity
        user.verified = True
        user.is_active = True
        user.save(update_fields=["verified", "is_active"])
        
        # Consider redirecting to a front-end success page here instead of returning JSON
        # return Response({"detail": "Email verified successfully. You can now log in."})
        return Response({"detail": "Email verified successfully. You can now log in."}, status=status.HTTP_200_OK)


# ------------------------------------------------------------

# ============================================================
#   LOGIN VIEW (Refined)
# ============================================================
class LoginView(APIView):
    """
    Authenticate user and return JWT tokens if verified.
    Uses the serializer's validation to handle authentication logic.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        # The serializer.is_valid() will handle all validation, including authentication,
        # and raise exceptions (400, 401, 403) based on its logic.
        serializer.is_valid(raise_exception=True)
        
        # Extracted data from validated_data in serializer is now cleaner
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


# ------------------------------------------------------------

# ============================================================
#   REQUEST PASSWORD RESET VIEW
# ============================================================
class RequestPasswordResetView(generics.GenericAPIView):
    """Send password reset link to user's email."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # The logic to find the user and send the email is handled in the serializer's save() method
        # and we use the 'pass' logic to prevent enumeration attacks.
        try:
            serializer.save() 
        except (SMTPException, SMTPRecipientsRefused) as e:
            print(f"Password reset email failed (SMTP): {e}")
            # Still return a 200 OK to prevent enumeration, but log the error
            pass 
        except Exception as e:
            print(f"Password reset email failed (Unexpected): {e}")
            pass
            
        return Response(
            {"detail": "If an account with that email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )


# ------------------------------------------------------------

# ============================================================
#   PASSWORD RESET CONFIRM VIEW
# ============================================================
class ResetPasswordView(generics.GenericAPIView):
    """Confirm password reset using token and set new password."""

    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Password setting is handled in the serializer's save() method
        serializer.save()
        
        return Response({"detail": "Password reset successfully."}, status=status.HTTP_200_OK)


# ------------------------------------------------------------

# ============================================================
#   TOKEN VERIFY VIEW (Custom TokenVerifyView)
# ============================================================
class CustomTokenVerifyView(TokenVerifyView):
    """Verifies JWT token validity."""
    # No changes needed here, as it inherits the best default behavior.
    permission_classes = [permissions.AllowAny]