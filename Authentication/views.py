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
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        """Handle Google OAuth callback with authorization code"""
        code = request.data.get('code')
        
        if not code:
            return Response(
                {"detail": "Authorization code is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            import requests
            from google.oauth2 import id_token
            from google.auth.transport import requests as google_requests
            
            # Get configuration from settings
            client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID')
            client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET')
            frontend_url = getattr(settings, 'FRONTEND_URL')
            
            # Exchange authorization code for tokens
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                'code': code,
                'client_id': client_id,
                'client_secret': client_secret,
                'redirect_uri': f"{frontend_url}/auth/google/callback",
                'grant_type': 'authorization_code',
            }
            
            token_response = requests.post(token_url, data=token_data)
            token_json = token_response.json()
            
            if token_response.status_code != 200:
                print(f"Token exchange failed: {token_json}")
                return Response(
                    {"detail": "Failed to exchange authorization code for tokens."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Get and verify ID token
            id_token_str = token_json.get('id_token')
            idinfo = id_token.verify_oauth2_token(
                id_token_str, 
                google_requests.Request(), 
                client_id
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
            
        except Exception as e:
            print(f"Google authentication error: {e}")
            return Response(
                {"detail": f"Google authentication failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
            
            
class AppleAuthView(APIView):
    """
    Handle Apple OAuth authentication.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        authorization_code = request.data.get('code')
        identity_token = request.data.get('id_token')
        user_data = request.data.get('user', {})
        
        if not authorization_code and not identity_token:
            return Response(
                {"detail": "Authorization code or identity token is required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            # For Apple Sign In, you need to:
            # 1. Validate the identity token (JWT)
            # 2. Exchange authorization code for tokens (if code is provided)
            # 3. Get user information
            
            # Note: This is a simplified implementation
            # In production, you need proper Apple JWT validation
            
            # Extract email from identity token or user data
            email = None
            
            # If we have an identity token, we can extract email from it
            if identity_token:
                try:
                    # In production, you would properly validate the JWT
                    # using Apple's public keys
                    import jwt
                    # This is just for decoding - proper validation required
                    decoded = jwt.decode(identity_token, options={"verify_signature": False})
                    email = decoded.get('email')
                except Exception as e:
                    print(f"Error decoding Apple identity token: {e}")
            
            # If no email from token, check user data
            if not email and user_data:
                email = user_data.get('email')
            
            if not email:
                return Response(
                    {"detail": "Could not retrieve email from Apple Sign In."},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Extract name from user data (Apple provides this only on first login)
            name_info = user_data.get('name', {})
            first_name = name_info.get('firstName', '')
            last_name = name_info.get('lastName', '')
            
            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'verified': True,  # Apple users are automatically verified
                    'is_active': True,
                }
            )
            
            # Update name if it's the first time and we have name data
            if created and (first_name or last_name):
                user.first_name = first_name
                user.last_name = last_name
                user.save()
            
            # Generate JWT tokens
            refresh = RefreshToken.for_user(user)
            
            return Response({
                'refresh': str(refresh),
                'access': str(refresh.access_token),
                'user': UserSerializer(user).data,
                'created': created
            })
            
        except Exception as e:
            print(f"Apple authentication error: {e}")
            return Response(
                {"detail": f"Apple authentication failed: {str(e)}"},
                status=status.HTTP_400_BAD_REQUEST
            )

class SocialAuthView(APIView):
    """
    Generic social authentication view.
    """
    permission_classes = [permissions.AllowAny]
    
    def post(self, request):
        provider = request.data.get('provider')
        access_token = request.data.get('access_token')
        email = request.data.get('email')
        first_name = request.data.get('first_name', '')
        last_name = request.data.get('last_name', '')
        
        if not provider or not access_token:
            return Response(
                {"detail": "Provider and access token are required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not email:
            return Response(
                {"detail": "Email is required for social authentication."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Get or create user
            user, created = User.objects.get_or_create(
                email=email,
                defaults={
                    'first_name': first_name,
                    'last_name': last_name,
                    'verified': True,  # Social auth users are automatically verified
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
            
        except Exception as e:
            print(f"Social authentication error: {e}")
            return Response(
                {"detail": f"{provider.title()} authentication failed."},
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
            print(f"Token blacklisting failed: {e}")
            
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