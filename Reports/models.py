import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from Location.models import County, SubCounty, Ward
from Departments.models import CountyDepartment


# ============================================================
#   REPORT STATUS CHOICES
# ============================================================
class ReportStatusChoices(models.TextChoices):
    """Defines the different states a report can pass through."""
    SUBMITTED = "submitted", "Submitted"
    VERIFIED = "verified", "Verified (AI confirmed)"
    PENDING = "pending", "Pending (awaiting county review)"
    NOTED = "noted", "Noted (official has seen)"
    ON_PROGRESS = "on_progress", "On Progress (being addressed)"
    RESOLVED = "resolved", "Resolved"
    REJECTED = "rejected", "Rejected (invalid or duplicate)"
    DELETED = "deleted", "Deleted"


# ============================================================
#   GOVERNMENT DEVELOPMENT STATUS CHOICES
# ============================================================
class DevelopmentStatusChoices(models.TextChoices):
    """Defines the status of government development projects."""
    PLANNED = "planned", "Planned"
    IN_PROGRESS = "in_progress", "In Progress"
    COMPLETED = "completed", "Completed"
    DELAYED = "delayed", "Delayed"
    CANCELLED = "cancelled", "Cancelled"


# ============================================================
#   REPORT IMAGE MODEL
# ============================================================
class ReportImage(models.Model):
    """
    Stores images related to a report.
    A report can have multiple images uploaded by the user as proof.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        "Report",
        on_delete=models.CASCADE,
        related_name="images",
        help_text="Report this image belongs to."
    )
    image = models.ImageField(
        upload_to="report_images/",
        help_text="Uploaded image (from camera or gallery)."
    )
    caption = models.CharField(
        max_length=255,
        blank=True,
        help_text="Optional description for the image."
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-uploaded_at"]
        verbose_name = "Report Image"
        verbose_name_plural = "Report Images"

    def __str__(self):
        return f"Image for {self.report.title}"


# ============================================================
#   REPORT MODEL (UPDATED WITH SOCIAL FEATURES)
# ============================================================
class Report(models.Model):
    """
    Represents an issue reported by a citizen or official.

    Each report captures:
    - Reporter info (linked to CustomUser)
    - Title, description, and optional images
    - Exact location (County, Subcounty, Ward, GPS)
    - Automatically or manually assigned department
    - Status flow (Submitted → Verified → Pending → Noted → On Progress → Resolved)
    - AI-based verification and confidence score
    - Social engagement features (likes, comments, views)
    - Government response system
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # --- Reporter Info ---
    reporter = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="reports",
        help_text="User who created this report."
    )
    role_at_submission = models.CharField(
        max_length=32,
        help_text="Snapshot of the reporter's role when submitting (e.g. citizen)."
    )

    # --- Main Report Details ---
    title = models.CharField(max_length=255, help_text="Short summary of the issue.")
    description = models.TextField(help_text="Detailed explanation of the issue.")

    # --- Location Data ---
    county = models.ForeignKey(
        County, on_delete=models.PROTECT, related_name="reports"
    )
    subcounty = models.ForeignKey(
        SubCounty, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports"
    )
    ward = models.ForeignKey(
        Ward, on_delete=models.SET_NULL, null=True, blank=True, related_name="reports"
    )
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Latitude from GPS (auto-filled from Check My Location)."
    )
    longitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True,
        help_text="Longitude from GPS (auto-filled from Check My Location)."
    )

    # --- Department ---
    department = models.ForeignKey(
        CountyDepartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reports",
        help_text="County department responsible for this issue (auto-detected by AI)."
    )

    # --- AI Verification ---
    verified_by_ai = models.BooleanField(
        default=False,
        help_text="True if the AI verified this report automatically."
    )
    ai_confidence = models.FloatField(
        null=True, blank=True,
        help_text="Confidence score from AI model (0.0–1.0)."
    )
    image_required_passed = models.BooleanField(
        default=False,
        help_text="True if required image evidence was provided."
    )

    # --- Status Tracking ---
    status = models.CharField(
        max_length=20,
        choices=ReportStatusChoices.choices,
        default=ReportStatusChoices.SUBMITTED,
        help_text="Current state of this report in the workflow."
    )

    # --- SOCIAL ENGAGEMENT FIELDS ---
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_reports",
        blank=True,
        help_text="Users who liked this report"
    )
    likes_count = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)

    # --- GOVERNMENT RESPONSE FIELDS ---
    government_response = models.TextField(
        blank=True,
        null=True,
        help_text="Official government response to this report"
    )
    response_date = models.DateTimeField(
        blank=True,
        null=True,
        help_text="When the government responded"
    )
    responded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responded_reports",
        help_text="Official who provided the response"
    )

    # --- DEVELOPMENT SHOWCASE FIELDS ---
    is_development_showcase = models.BooleanField(
        default=False,
        help_text="Mark as true if this report showcases government development work"
    )
    development_budget = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Budget allocated for this development (if applicable)"
    )
    completion_date = models.DateField(
        null=True,
        blank=True,
        help_text="Expected or actual completion date"
    )
    development_progress = models.IntegerField(
        default=0,
        help_text="Progress percentage (0-100)"
    )

    # --- Metadata & Audit ---
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True)
    deleted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deleted_reports",
        help_text="User who deleted the report (soft delete)."
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Report"
        verbose_name_plural = "Reports"
        indexes = [
            models.Index(fields=['status', 'created_at']),
            models.Index(fields=['county', 'status']),
            models.Index(fields=['department', 'created_at']),
            models.Index(fields=['is_development_showcase', 'created_at']),
        ]

    def __str__(self):
        return f"{self.title} ({self.county.name})"
    
    # ---------------------------------------------------------------------
    #   Helper Methods
    # ---------------------------------------------------------------------
    def soft_delete(self, user=None):
        """Marks the report as deleted without actually removing it."""
        self.status = ReportStatusChoices.DELETED
        self.deleted_at = timezone.now()
        if user:
            self.deleted_by = user
        self.save(update_fields=["status", "deleted_at", "deleted_by"])

    def is_editable_by_reporter(self):
        """Reporter can edit only before it's verified."""
        return self.status == ReportStatusChoices.SUBMITTED

    def mark_verified(self, confidence=None):
        """Used when AI verification passes."""
        self.verified_by_ai = True
        self.status = ReportStatusChoices.VERIFIED
        if confidence:
            self.ai_confidence = confidence
        self.save(update_fields=["verified_by_ai", "status", "ai_confidence"])

    def mark_status(self, new_status):
        """Safely update status with validation."""
        valid_statuses = [choice[0] for choice in ReportStatusChoices.choices]
        if new_status not in valid_statuses:
            raise ValueError(f"Invalid status: {new_status}")
        self.status = new_status
        self.save(update_fields=["status"])

    def add_government_response(self, response_text, official):
        """Add government response to this report."""
        self.government_response = response_text
        self.response_date = timezone.now()
        self.responded_by = official
        self.save(update_fields=["government_response", "response_date", "responded_by"])

    def like(self, user):
        """Like this report."""
        if not self.likes.filter(id=user.id).exists():
            self.likes.add(user)
            self.likes_count += 1
            self.save(update_fields=["likes_count"])
            return True
        return False

    def unlike(self, user):
        """Unlike this report."""
        if self.likes.filter(id=user.id).exists():
            self.likes.remove(user)
            self.likes_count = max(0, self.likes_count - 1)
            self.save(update_fields=["likes_count"])
            return True
        return False

    def increment_views(self):
        """Increment view count."""
        self.views_count += 1
        self.save(update_fields=["views_count"])
        
    def get_status_display(self):
        """Return human-readable status name."""
        return dict(ReportStatusChoices.choices).get(self.status, self.status)

    def mark_as_development_showcase(self, budget=None, completion_date=None):
        """Mark this report as a development showcase."""
        self.is_development_showcase = True
        if budget:
            self.development_budget = budget
        if completion_date:
            self.completion_date = completion_date
        self.save(update_fields=["is_development_showcase", "development_budget", "completion_date"])

    @property
    def engagement_score(self):
        """Calculate engagement score based on likes, comments, and views."""
        return (self.likes_count * 2) + (self.comments_count * 3) + (self.views_count * 0.1)

    def clean(self):
        """Validate model data."""
        if self.is_development_showcase and not self.government_response:
            raise ValidationError("Development showcases must have a government response.")
        
        if self.completion_date and self.completion_date < timezone.now().date():
            raise ValidationError("Completion date cannot be in the past.")
        
        if self.development_budget and self.development_budget < 0:
            raise ValidationError("Budget cannot be negative.")


# ============================================================
#   GOVERNMENT DEVELOPMENT MODEL
# ============================================================
class GovernmentDevelopment(models.Model):
    """
    Showcase government projects and developments separately from reports.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Basic Information
    title = models.CharField(max_length=255, help_text="Title of the development project")
    description = models.TextField(help_text="Detailed description of the project")
    
    # Location and Department
    county = models.ForeignKey(
        County, on_delete=models.CASCADE, related_name="developments"
    )
    department = models.ForeignKey(
        CountyDepartment, on_delete=models.CASCADE, related_name="developments"
    )
    
    # Project Details
    budget = models.DecimalField(
        max_digits=12, 
        decimal_places=2, 
        null=True, 
        blank=True,
        help_text="Total budget allocated for this project"
    )
    start_date = models.DateField(help_text="Project start date")
    expected_completion = models.DateField(
        null=True, 
        blank=True,
        help_text="Expected completion date"
    )
    actual_completion = models.DateField(
        null=True, 
        blank=True,
        help_text="Actual completion date"
    )
    status = models.CharField(
        max_length=20,
        choices=DevelopmentStatusChoices.choices,
        default=DevelopmentStatusChoices.PLANNED
    )
    
    # Progress Tracking
    progress_percentage = models.IntegerField(
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        help_text="Current progress percentage (0-100)"
    )
    progress_updates = models.TextField(
        blank=True,
        help_text="Regular updates on project progress"
    )
    
    # Media
    images = models.ManyToManyField(
        ReportImage,
        blank=True,
        help_text="Project images and progress photos"
    )
    
    # Social Engagement
    likes = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        related_name="liked_developments",
        blank=True
    )
    likes_count = models.IntegerField(default=0)
    comments_count = models.IntegerField(default=0)
    views_count = models.IntegerField(default=0)
    
    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="created_developments"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Government Development"
        verbose_name_plural = "Government Developments"
        indexes = [
            models.Index(fields=['county', 'status']),
            models.Index(fields=['department', 'created_at']),
            models.Index(fields=['status', 'expected_completion']),
        ]

    def __str__(self):
        return f"{self.title} - {self.county.name}"

    def update_progress(self, percentage, update_text=None):
        """Update project progress."""
        if not (0 <= percentage <= 100):
            raise ValidationError("Progress percentage must be between 0 and 100")
        
        self.progress_percentage = percentage
        
        if percentage == 100:
            self.status = DevelopmentStatusChoices.COMPLETED
            self.actual_completion = timezone.now().date()
        elif percentage > 0:
            self.status = DevelopmentStatusChoices.IN_PROGRESS
        
        if update_text:
            if self.progress_updates:
                self.progress_updates += f"\n\n{timezone.now().strftime('%Y-%m-%d')}: {update_text}"
            else:
                self.progress_updates = f"{timezone.now().strftime('%Y-%m-%d')}: {update_text}"
        
        self.save()

    def like(self, user):
        """Like this development."""
        if not self.likes.filter(id=user.id).exists():
            self.likes.add(user)
            self.likes_count += 1
            self.save(update_fields=["likes_count"])
            return True
        return False

    def unlike(self, user):
        """Unlike this development."""
        if self.likes.filter(id=user.id).exists():
            self.likes.remove(user)
            self.likes_count = max(0, self.likes_count - 1)
            self.save(update_fields=["likes_count"])
            return True
        return False

    def increment_views(self):
        """Increment view count."""
        self.views_count += 1
        self.save(update_fields=["views_count"])

    @property
    def is_overdue(self):
        """Check if project is overdue."""
        if self.expected_completion and self.status != DevelopmentStatusChoices.COMPLETED:
            return timezone.now().date() > self.expected_completion
        return False

    @property
    def days_remaining(self):
        """Calculate days remaining until expected completion."""
        if self.expected_completion and self.status != DevelopmentStatusChoices.COMPLETED:
            remaining = (self.expected_completion - timezone.now().date()).days
            return max(0, remaining)
        return None

    def clean(self):
        """Validate model data."""
        if self.expected_completion and self.expected_completion < self.start_date:
            raise ValidationError("Expected completion date cannot be before start date.")
        
        if self.actual_completion and self.actual_completion < self.start_date:
            raise ValidationError("Actual completion date cannot be before start date.")
        
        if self.budget and self.budget < 0:
            raise ValidationError("Budget cannot be negative.")


# ============================================================
#   REPORT LIKE MODEL (For tracking likes with timestamps)
# ============================================================
class ReportLike(models.Model):
    """
    Track report likes with timestamps for analytics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    report = models.ForeignKey(Report, on_delete=models.CASCADE, related_name="like_instances")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'report']
        ordering = ['-created_at']
        verbose_name = "Report Like"
        verbose_name_plural = "Report Likes"

    def __str__(self):
        return f"{self.user.email} liked {self.report.title}"


# ============================================================
#   DEVELOPMENT LIKE MODEL (For tracking development likes with timestamps)
# ============================================================
class DevelopmentLike(models.Model):
    """
    Track development project likes with timestamps for analytics.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    development = models.ForeignKey(GovernmentDevelopment, on_delete=models.CASCADE, related_name="like_instances")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ['user', 'development']
        ordering = ['-created_at']
        verbose_name = "Development Like"
        verbose_name_plural = "Development Likes"

    def __str__(self):
        return f"{self.user.email} liked {self.development.title}"