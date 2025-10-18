import uuid
from django.db import models
from django.utils import timezone
from django.conf import settings
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
#   REPORT MODEL
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
        """Reporter can edit only before it’s verified."""
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
        Report,
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