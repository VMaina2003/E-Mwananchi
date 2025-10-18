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