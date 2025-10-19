import uuid
from django.db import models
from django.conf import settings

# Import the Report model from your reports app
from Reports.models import Report


class Comment(models.Model):
    """
    Represents a comment made on a report.
    Can be from either a citizen or an official (admin/superadmin/county official).
    """

    class CommentType(models.TextChoices):
        CITIZEN = "citizen", "Citizen"
        OFFICIAL = "official", "Official"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    report = models.ForeignKey(
        Report, on_delete=models.CASCADE, related_name="comments"
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="comments"
    )
    comment_type = models.CharField(
        max_length=20, choices=CommentType.choices, default=CommentType.CITIZEN
    )
    content = models.TextField()
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
