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