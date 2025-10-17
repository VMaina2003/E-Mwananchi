from datetime import timedelta
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from rest_framework_simplejwt.tokens import AccessToken
from django.utils import timezone

def generate_verification_token(user):
    """Generate a time-limited JWT token for email verification."""
    token = AccessToken.for_user(user)
    token.set_exp(lifetime=timedelta(hours=0.5)) 
    token["email"] = user.email
    token["purpose"] = "email_verification"
    return str(token)


def verify_email_token(token):
    """Decode and validate the email verification token.
    Returns the user if valid, otherwise None.
    """
    from django.contrib.auth import get_user_model
    from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

    User = get_user_model()

    try:
        decoded = AccessToken(token)
        if decoded.get("purpose") != "email_verification":
            return None

        email = decoded.get("email")
        if not email:
            return None

        try:
            user = User.objects.get(email=email)
            return user
        except User.DoesNotExist:
            return None
    except (TokenError, InvalidToken):
        return None


def send_verification_email(user, request=None):
    token = generate_verification_token(user)
    verification_url = f"http://127.0.0.1:8000/api/auth/verify-email/?token={token}"

    subject = "Verify Your Email - E-Mwananchi"

    context = {
        "user": user,
        "verification_url": verification_url,
        "current_year": timezone.now().year,
    }

    html_message = render_to_string("Authentication/templates/email_verification.html", context)
    plain_message = strip_tags(html_message)

    from_email = getattr(settings, "DEFAULT_FROM_EMAIL", "e.mwananchi254@gmail.com")
    recipient_list = [user.email]

    send_mail(subject, plain_message, from_email, recipient_list, html_message=html_message)