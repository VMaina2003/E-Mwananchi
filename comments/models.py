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
    
    # Control and timestamps
    is_deleted = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment by {self.user.email} on {self.report.title}"

    def can_delete(self, user):
        """
        Determines if the given user is allowed to delete this comment.
        """
        return (
            user == self.user
            or user.is_admin
            or user.is_superadmin
            or user.is_county_official
        )