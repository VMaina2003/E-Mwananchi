from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

# Import your utility functions
from .utils import (
    verify_email_token,
    verify_password_reset_token,
    send_password_reset_email, # Kept for 'save' method, though its usage is often better in the view/manager
)

User = get_user_model()


# ============================================================
#   USER SERIALIZER
# ============================================================
class UserSerializer(serializers.ModelSerializer):
    """Standard serializer for returning user data."""
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name",
            "last_name",
            "role",
            "verified",
            "is_active",
            "date_joined",
        ]
        read_only_fields = ["id", "verified", "is_active", "date_joined", "role"]


# ============================================================
#   REGISTER SERIALIZER
# ============================================================
class RegisterSerializer(serializers.ModelSerializer):
    """Handles user creation with password confirmation and validation."""
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = [
            "email",
            "first_name",
            "last_name",
            "password",
            "confirm_password",
        ]
        extra_kwargs = {
            "password": {"write_only": True, "min_length": 8}, # Added min_length hint
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            # Use the standard 'unique' error code
            raise serializers.ValidationError("This email is already registered.", code='unique')
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)

        if password != confirm_password:
            # Raise a field-specific error for better client handling
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        # This will raise a DRF ValidationError if Django's password validators fail
        # This is correct.
        validate_password(password) 
        return attrs

    def create(self, validated_data):
        """Create inactive, unverified user."""
        # Ensure 'password' field is passed to create_user
        password = validated_data.pop("password") 
        
        user = User.objects.create_user(
            **validated_data, # Pass remaining fields
            password=password,
            is_active=False,
            verified=False,
            role=User.Roles.CITIZEN, # Assuming User.Roles.CITIZEN is defined
        )
        return user


# ============================================================
#   EMAIL VERIFICATION SERIALIZER
# ============================================================
class EmailVerificationSerializer(serializers.Serializer):
    """Validates the email verification token."""
    token = serializers.CharField()

    def validate(self, attrs):
        token = attrs.get("token")
        user = verify_email_token(token)

        if not user:
            # Use a standard 'invalid' code
            raise serializers.ValidationError({"token": "Invalid or expired verification link."}, code='invalid')
        
        if user.verified:
            # Although the view handles this, the serializer can preemptively validate
            raise serializers.ValidationError({"token": "Email is already verified."}, code='invalid')
            
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        # The save logic is clean and correct
        user.verified = True
        user.is_active = True
        user.save(update_fields=["verified", "is_active"])
        return user


# ============================================================
#   LOGIN SERIALIZER (Refined)
# ============================================================
class LoginSerializer(serializers.Serializer):
    """
    Handles user authentication and JWT token generation.
    Returns tokens and user data upon success.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(write_only=True, required=True)
    
    # These fields are included in the output of validate() but are not used for input
    # They are kept here for clear documentation of the output structure
    access = serializers.CharField(read_only=True) 
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        # Pass request context if available to Django's authenticate
        request = self.context.get('request')
        user = authenticate(request=request, email=email, password=password)

        if not user:
            # Use a non-field error key for a general login failure
            raise serializers.ValidationError({"detail": "Invalid email or password."}, code='authentication')
            
        if not user.verified:
            # Use a non-field error key for a general login failure
            raise serializers.ValidationError({"detail": "Account is not verified. Please check your email."}, code='permission_denied')
            
        if not user.is_active:
            # This generally shouldn't happen if verified=True, but keeps the check clear
            raise serializers.ValidationError({"detail": "Account is inactive."}, code='permission_denied')

        refresh = RefreshToken.for_user(user)
        
        # Return the final data structure the view should respond with
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "user": UserSerializer(user).data,
        }


# ============================================================
#   PASSWORD RESET REQUEST SERIALIZER
# ============================================================
class PasswordResetRequestSerializer(serializers.Serializer):
    """Validates the email and initiates the password reset process."""
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            # Store the user object on the serializer instance
            self.user = User.objects.get(email=value)
        except User.DoesNotExist:
            # IMPORTANT: Do NOT raise an error here. 
            # This prevents email enumeration attacks (telling an attacker which emails exist).
            # We simply return the value, and the view will handle the sending attempt (or skip it).
            self.user = None
        return value

    def save(self):
        # Only attempt to send if a user was found
        if self.user:
            send_password_reset_email(self.user)
        # Return None or user, depending on what the view expects
        return self.user


# ============================================================
#   PASSWORD RESET CONFIRM SERIALIZER
# ============================================================
class PasswordResetConfirmSerializer(serializers.Serializer):
    """Handles token validation and new password setting."""
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")
        token = attrs.get("token")

        if new_password != confirm_password:
            # Raise a field-specific error
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        user = verify_password_reset_token(token)
        if not user:
            raise serializers.ValidationError({"token": "Invalid or expired token."}, code='invalid')

        validate_password(new_password)
        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]
        
        # The logic is correct, but update_fields is optional if only 'password' is changed
        user.set_password(new_password)
        user.save(update_fields=["password"]) 
        return user