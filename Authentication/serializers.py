from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from rest_framework import serializers
from rest_framework_simplejwt.tokens import RefreshToken
from .utils import (
    send_verification_email,
    verify_email_token,
    generate_password_reset_token,
    verify_password_reset_token,
    send_password_reset_email,
)

User = get_user_model()


# ============================================================
#   USER SERIALIZER
# ============================================================
class UserSerializer(serializers.ModelSerializer):
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
        read_only_fields = ["id", "verified", "is_active", "date_joined"]


# ============================================================
#   REGISTER SERIALIZER
# ============================================================
class RegisterSerializer(serializers.ModelSerializer):
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
            "password": {"write_only": True},
        }

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists.")
        return value

    def validate(self, attrs):
        password = attrs.get("password")
        confirm_password = attrs.pop("confirm_password", None)

        if password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")

        validate_password(password)
        return attrs

    def create(self, validated_data):
        """Create inactive, unverified user."""
        user = User.objects.create_user(
            email=validated_data["email"],
            first_name=validated_data.get("first_name", ""),
            last_name=validated_data.get("last_name", ""),
            password=validated_data["password"],
            is_active=False,
            verified=False,
            role=User.Roles.CITIZEN,
        )
        return user



# ============================================================
#   EMAIL VERIFICATION SERIALIZER
# ============================================================
class EmailVerificationSerializer(serializers.Serializer):
    token = serializers.CharField()

    def validate(self, attrs):
        token = attrs.get("token")
        user = verify_email_token(token)

        if not user:
            raise serializers.ValidationError("Invalid or expired verification link.")
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        user = self.validated_data["user"]
        user.verified = True
        user.is_active = True
        user.save(update_fields=["verified", "is_active"])
        return user


# ============================================================
#   LOGIN SERIALIZER
# ============================================================
class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    access = serializers.CharField(read_only=True)
    refresh = serializers.CharField(read_only=True)
    user = UserSerializer(read_only=True)

    def validate(self, attrs):
        email = attrs.get("email")
        password = attrs.get("password")

        user = authenticate(email=email, password=password)

        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_active or not user.verified:
            raise serializers.ValidationError("Please verify your email before logging in.")

        refresh = RefreshToken.for_user(user)
        attrs["refresh"] = str(refresh)
        attrs["access"] = str(refresh.access_token)
        attrs["user"] = user
        return attrs


# ============================================================
#   PASSWORD RESET REQUEST SERIALIZER
# ============================================================
class PasswordResetRequestSerializer(serializers.Serializer):
    email = serializers.EmailField()

    def validate_email(self, value):
        try:
            self.user = User.objects.get(email=value)
        except User.DoesNotExist:
            raise serializers.ValidationError("No account found with this email.")
        return value

    def save(self):
        user = self.user
        send_password_reset_email(user)
        return user


# ============================================================
#   PASSWORD RESET CONFIRM SERIALIZER
# ============================================================
class PasswordResetConfirmSerializer(serializers.Serializer):
    token = serializers.CharField()
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        token = attrs.get("token")
        new_password = attrs.get("new_password")
        confirm_password = attrs.get("confirm_password")

        if new_password != confirm_password:
            raise serializers.ValidationError("Passwords do not match.")

        user = verify_password_reset_token(token)
        if not user:
            raise serializers.ValidationError("Invalid or expired token.")

        validate_password(new_password)
        attrs["user"] = user
        return attrs

    def save(self):
        user = self.validated_data["user"]
        new_password = self.validated_data["new_password"]
        user.set_password(new_password)
        user.save(update_fields=["password"])
        return user
