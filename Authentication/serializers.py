from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken

from .utils import (
    verify_email_token,
    verify_password_reset_token,
    send_password_reset_email,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """
    Standard serializer for user data with role display.
    """
    role_display = serializers.CharField(source='get_role_display', read_only=True)
    
    class Meta:
        model = User
        fields = [
            "id",
            "email",
            "first_name", 
            "last_name",
            "role",
            "role_display",
            "verified",
            "is_active",
            "date_joined",
            "county",
        ]
        read_only_fields = [
            "id", "verified", "is_active", "date_joined", 
            "role", "role_display", "county"
        ]


class RegisterSerializer(serializers.ModelSerializer):
    """
    Handles user registration with validation.
    """
    confirm_password = serializers.CharField(
        write_only=True,
        min_length=8,
        error_messages={
            'min_length': 'Password must be at least 8 characters long.'
        }
    )
    password = serializers.CharField(
        write_only=True, 
        min_length=8,
        error_messages={
            'min_length': 'Password must be at least 8 characters long.'
        }
    )

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
            'email': {'required': True},
            'first_name': {'required': True},
            'last_name': {'required': True},
        }

    def validate_email(self, value):
        """
        Validate email uniqueness.
        """
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError(
                "A user with this email already exists."
            )
        return value.lower()

    def validate(self, attrs):
        """
        Validate password match and strength.
        """
        password = attrs.get('password')
        confirm_password = attrs.get('confirm_password')

        if password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })

        # Validate password strength
        validate_password(password)
        
        # Remove confirm_password as it's not needed for user creation
        attrs.pop('confirm_password')
        return attrs

    def create(self, validated_data):
        """
        Create a new user with citizen role.
        """
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            **validated_data,
            password=password,
            is_active=False,
            verified=False,
            role=User.Roles.CITIZEN,
        )
        return user


class LoginSerializer(serializers.Serializer):
    """
    Handles user authentication and JWT token generation.
    """
    email = serializers.EmailField(required=True)
    password = serializers.CharField(
        write_only=True, 
        required=True,
        trim_whitespace=False
    )
    
    # Response fields
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    def validate(self, attrs):
        """
        Authenticate user and generate tokens.
        """
        email = attrs.get('email').lower()
        password = attrs.get('password')
        request = self.context.get('request')

        # Authenticate user
        user = authenticate(
            request=request, 
            email=email, 
            password=password
        )

        if not user:
            raise serializers.ValidationError({
                'detail': 'Invalid email or password.'
            })
            
        if not user.verified:
            raise serializers.ValidationError({
                'detail': 'Please verify your email before logging in.'
            })
            
        if not user.is_active:
            raise serializers.ValidationError({
                'detail': 'This account has been deactivated.'
            })

        # Generate tokens
        refresh = RefreshToken.for_user(user)
        
        return {
            'refresh': str(refresh),
            'access': str(refresh.access_token),
            'user': UserSerializer(user).data,
        }


class PasswordResetRequestSerializer(serializers.Serializer):
    """
    Handles password reset request validation.
    """
    email = serializers.EmailField(required=True)

    def validate_email(self, value):
        """
        Validate email exists without revealing information.
        """
        try:
            self.user = User.objects.get(email=value.lower(), is_active=True)
        except User.DoesNotExist:
            self.user = None
        return value

    def save(self):
        """
        Send password reset email if user exists.
        """
        if self.user and self.user.verified:
            send_password_reset_email(self.user)
        return self.user


class PasswordResetConfirmSerializer(serializers.Serializer):
    """
    Handles password reset confirmation.
    """
    token = serializers.CharField(required=True)
    new_password = serializers.CharField(
        write_only=True, 
        required=True,
        min_length=8
    )
    confirm_password = serializers.CharField(
        write_only=True, 
        required=True,
        min_length=8
    )

    def validate(self, attrs):
        """
        Validate token and password match.
        """
        token = attrs.get('token')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        # Check password match FIRST
        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': 'Passwords do not match.'
            })

        # Validate token BEFORE password validation
        user = verify_password_reset_token(token)
        if not user:
            raise serializers.ValidationError({
                'token': 'Invalid or expired reset token.'
            })

        # Validate password strength - this should show specific errors
        try:
            validate_password(new_password)
        except ValidationError as e:
            raise serializers.ValidationError({
                'new_password': list(e.messages)  # This returns specific password errors
            })
        
        attrs['user'] = user
        return attrs

    def save(self):
        """
        Update user password.
        """
        user = self.validated_data['user']
        new_password = self.validated_data['new_password']
        
        user.set_password(new_password)
        user.save(update_fields=['password'])
        return user


class EmailVerificationSerializer(serializers.Serializer):
    """
    Validates email verification token.
    """
    token = serializers.CharField(required=True)

    def validate(self, attrs):
        """
        Validate verification token.
        """
        token = attrs.get('token')
        user = verify_email_token(token)

        if not user:
            raise serializers.ValidationError({
                'token': 'Invalid or expired verification token.'
            })
        
        if user.verified:
            raise serializers.ValidationError({
                'token': 'Email is already verified.'
            })
            
        attrs['user'] = user
        return attrs

    def save(self):
        """
        Mark user as verified.
        """
        user = self.validated_data['user']
        user.verified = True
        user.is_active = True
        user.save(update_fields=['verified', 'is_active'])
        return user