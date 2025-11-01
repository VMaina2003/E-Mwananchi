from django.contrib.auth import authenticate, get_user_model
from django.conf import settings
from rest_framework import status, generics, permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenVerifyView
from smtplib import SMTPException, SMTPRecipientsRefused

# Import your serializers and utils
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    PasswordResetRequestSerializer,
    PasswordResetConfirmSerializer,
    UserSerializer,
)
from .utils import (
    verify_email_token,
    send_verification_email,
    send_password_reset_email,
    verify_password_reset_token,
)

User = get_user_model()


class RegisterView(generics.CreateAPIView):
    """
    Handles user registration with email verification.
    """
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
                    {
                        "message": "Account created successfully. Please check your email to verify your account.",
                        "email": user.email
                    },
                    status=status.HTTP_201_CREATED,
                )
            else:
                user.delete()
                return Response(
                    {"detail": "Verification email could not be sent. Please try again later."},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
                
        except (SMTPException, SMTPRecipientsRefused) as e:
            user.delete()
            return Response(
                {"detail": "Email service temporarily unavailable. Please try again later."},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        except Exception as e:
            user.delete()
            return Response(
                {"detail": "An unexpected error occurred during registration."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class VerifyEmailView(APIView):
    """
    Verify user's email through token link.
    """
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        token = request.GET.get("token")
        
        if not token:
            return Response(
                {"detail": "Verification token is missing."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        user = verify_email_token(token)
        if not user:
            return Response(
                {"detail": "Invalid or expired verification token."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if user.verified:
            return Response(
                {"detail": "Email is already verified."},
                status=status.HTTP_200_OK
            )

        user.verified = True
        user.is_active = True
        user.save(update_fields=["verified", "is_active"])
        
        return Response(
            {"detail": "Email verified successfully. You can now log in."},
            status=status.HTTP_200_OK
        )


class LoginView(APIView):
    """
    Authenticate user and return JWT tokens.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        serializer = LoginSerializer(
            data=request.data, 
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data, status=status.HTTP_200_OK)


class RequestPasswordResetView(generics.GenericAPIView):
    """
    Send password reset link to user's email.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetRequestSerializer
    
    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            serializer.save()
        except (SMTPException, SMTPRecipientsRefused) as e:
            print(f"Password reset email failed: {e}")
        except Exception as e:
            print(f"Unexpected error in password reset: {e}")
            
        return Response(
            {"detail": "If an account with that email exists, a password reset link has been sent."},
            status=status.HTTP_200_OK,
        )


class ResetPasswordView(generics.GenericAPIView):
    """
    Confirm password reset using token and set new password.
    """
    permission_classes = [permissions.AllowAny]
    serializer_class = PasswordResetConfirmSerializer

    def post(self, request):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        
        return Response(
            {"detail": "Password reset successfully."},
            status=status.HTTP_200_OK
        )


class CurrentUserView(APIView):
    """
    Get current authenticated user data.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request):
        serializer = UserSerializer(request.user)
        return Response(serializer.data)


class GoogleAuthView(APIView):
    """
    Handle Google OAuth authentication.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        access_token = request.data.get('access_token')
        
        if not access_token:
            return Response(
                {"detail": "Access token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # Verify Google token
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            
            idinfo = id_token.verify_oauth2_token(
                access_token, 
                google_requests.Request(), 
                settings.GOOGLE_OAUTH_CLIENT_ID
            )
            
            # Get or create user
            email = idinfo['email']
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': idinfo.get('given_name', ''),
                    'last_name': idinfo.get('family_name', ''),
                    'verified': True,
                    'is_active': True,
                }
            )
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data,
                'created': created
            })
            
        except ValueError:
            return Response(
                {"detail": "Invalid Google token."},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            return Response(
                {"detail": "Google authentication failed."},
                status=status.HTTP_400_BAD_REQUEST
            )


class LogoutView(APIView):
    """
    Handle user logout with token blacklisting.
    """
    permission_classes = [permissions.IsAuthenticated]
    
    def post(self, request):
        try:
            refresh_token = request.data.get('refresh_token')
            if refresh_token:
                token = RefreshToken(refresh_token)
                token.blacklist()
        except Exception as e:
            # Even if blacklisting fails, we consider logout successful
            pass
            
        return Response(
            {"detail": "Successfully logged out."},
            status=status.HTTP_200_OK
        )

class ResendVerificationEmailView(APIView):
    """Resend email verification link."""
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        email = request.data.get('email')
        if not email:
            return Response(
                {"detail": "Email is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            user = User.objects.get(email=email.lower())
            if user.verified:
                return Response(
                    {"detail": "Email is already verified."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            email_sent = send_verification_email(user)
            if email_sent:
                return Response(
                    {"detail": "Verification email sent successfully."},
                    status=status.HTTP_200_OK
                )
            else:
                return Response(
                    {"detail": "Failed to send verification email."},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR
                )
                
        except User.DoesNotExist:
            # Don't reveal whether email exists
            return Response(
                {"detail": "If an account with that email exists, a verification link has been sent."},
                status=status.HTTP_200_OK
            )

class CustomTokenVerifyView(TokenVerifyView):
    """
    Verify JWT token validity.
    """
    permission_classes = [permissions.AllowAny]