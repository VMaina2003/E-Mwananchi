import uuid
from django.db import models
from django.conf import settings
from Reports.models import Report


class Notification(models.Model):
    """
    Represents a notification sent to a user when an event occurs.
    (e.g., comment on report, report status change, etc.)
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="notifications",
        help_text="User who receives this notification."
    )
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications_sent",
        help_text="User who triggered this notification (e.g., commenter, official)."
    )
    verb = models.CharField(
        max_length=255,
        help_text="Short description of what happened (e.g. 'commented on your report')."
    )
    description = models.TextField(
        blank=True,
        help_text="Optional additional context or message body."
    )

    target_report = models.ForeignKey(
        Report,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
        help_text="Report that this notification is related to, if any."
    )

    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Notification"
        verbose_name_plural = "Notifications"

    def __str__(self):
        return f"{self.recipient.email} - {self.verb}"

    def mark_as_read(self):
        """Mark the notification as read."""
        self.is_read = True
        self.save(update_fields=["is_read"])
