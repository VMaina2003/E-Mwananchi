from uuid import uuid4

from django.contrib.auth.base_user import BaseUserManager
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    """Custom user manager where email is the unique identifiers
    for authentication instead of usernames.

    Methods
    -------
    create_user(email, password=None, **extra_fields)
        Create and save a regular User with the given email and password.

    create_superuser(email, password, **extra_fields)
        Create and save a SuperUser with the given email and password.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        now = timezone.now()
        user = self.model(email=email, date_joined=now, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        # Default for regular users: inactive & unverified until email verification
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        extra_fields.setdefault("is_active", False)
        extra_fields.setdefault("verified", False)

        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("verified", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")

        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """Custom User model.

    - Uses email as the unique identifier for authentication
    - Uses UUID primary key for safer external references
    - Includes a `role` TextChoices for the app roles
    - `verified` controls whether the user confirmed their email
    """

    class Roles(models.TextChoices):
        CITIZEN = "citizen", "Citizen"
        VIEWER = "viewer", "Viewer"
        COUNTY_OFFICIAL = "county_official", "County Official"
        ADMIN = "admin", "Admin"
        SUPERADMIN = "superadmin", "Super Admin"

    id = models.UUIDField(primary_key=True, default=uuid4, editable=False)
    email = models.EmailField("email address", unique=True)

    # Optional profile fields
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)

    role = models.CharField(
        max_length=32, choices=Roles.choices, default=Roles.CITIZEN
    )

    # Account state
    verified = models.BooleanField(
        default=False, help_text="True when user has verified their email"
    )
    is_active = models.BooleanField(
        default=False, help_text="Designates whether this user should be treated as active."
    )
    is_staff = models.BooleanField(
        default=False, help_text="Designates whether the user can log into this admin site."
    )

    # Timestamps
    date_joined = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    class Meta:
        verbose_name = "user"
        verbose_name_plural = "users"

    def __str__(self):
        return self.email

    def get_full_name(self):
        """Return the first_name plus the last_name, with a space in between."""
        full_name = f"{self.first_name or ''} {self.last_name or ''}".strip()
        return full_name or self.email

    def get_short_name(self):
        """Return the short name for the user."""
        return self.first_name or self.email.split("@")[0]

    # Convenience helpers
    @property
    def is_citizen(self):
        return self.role == self.Roles.CITIZEN

    @property
    def is_viewer(self):
        return self.role == self.Roles.VIEWER

    @property
    def is_county_official(self):
        return self.role == self.Roles.COUNTY_OFFICIAL

    @property
    def is_admin(self):
        return self.role == self.Roles.ADMIN

    @property
    def is_superadmin(self):
        return self.role == self.Roles.SUPERADMIN
