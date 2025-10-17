from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.utils import timezone
from django.urls import reverse
from rest_framework_simplejwt.tokens import AccessToken
from django.contrib.auth import get_user_model

User = get_user_model()

# ============================================================
#   EMAIL VERIFICATION UTILITIES
# ============================================================

def generate_verification_token(user):
    """Generate a time-limited JWT token for email verification."""
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(hours=24))
    token["email"] = user.email
    token["purpose"] = "email_verification"
    return str(token)


def verify_email_token(token):
    """Validate the email verification token and return user if valid."""
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

    try:
        decoded = AccessToken(token)
        if decoded.get("purpose") != "email_verification":
            return None
        email = decoded.get("email")
        if not email:
            return None
        return User.objects.filter(email=email).first()
    except (TokenError, InvalidToken):
        return None


def send_verification_email(user, request=None):
    """Send HTML email with verification link."""
    token = generate_verification_token(user)
    verification_url = f"http://127.0.0.1:8000/api/auth/verify-email/?token={token}"

    subject = "Verify Your Email - E-Mwananchi"
    context = {
        "user": user,
        "verification_url": verification_url,
        "current_year": timezone.now().year,
    }

    html_message = render_to_string("Authentication/email_verification.html", context)
    plain_message = strip_tags(html_message)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "e.mwananchi254@gmail.com")
    recipient_list = [user.email]

    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
    return True


# ============================================================
#   PASSWORD RESET UTILITIES
# ============================================================

def generate_password_reset_token(user):
    """Generate a 0.5-hour JWT token for password reset."""
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(hours=0.5))
    token["email"] = user.email
    token["purpose"] = "password_reset"
    return str(token)


def verify_password_reset_token(token):
    """Validate password reset token and return user if valid."""
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

    try:
        decoded = AccessToken(token)
        if decoded.get("purpose") != "password_reset":
            return None
        email = decoded.get("email")
        if not email:
            return None
        return User.objects.filter(email=email).first()
    except (TokenError, InvalidToken):
        return None


def send_password_reset_email(user):
    """Send an HTML email with password reset link."""
    token = generate_password_reset_token(user)
    reset_url = f"http://127.0.0.1:8000/api/auth/reset-password/?token={token}"

    subject = "Reset Your Password - E-Mwananchi"
    context = {
        "user": user,
        "reset_url": reset_url,
        "current_year": timezone.now().year,
    }

    html_message = render_to_string("Authentication/password_reset_email.html", context)
    plain_message = strip_tags(html_message)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "e.mwananchi254@gmail.com")
    recipient_list = [user.email]

    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)
    return True
