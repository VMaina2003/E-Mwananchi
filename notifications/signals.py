from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Notification
from Reports.models import Report
from comments.models import Comment
from Authentication.models import CustomUser


# ============================================================
#   REPORT CREATED — Notify Admins/Officials
# ============================================================
@receiver(post_save, sender=Report)
def notify_on_new_report(sender, instance, created, **kwargs):
    """
    When a new report is submitted by a citizen:
    → Notify all Admins and County Officials in that county.
    """
    if created:
        county = instance.county
        reporter = instance.created_by

        # Get all officials/admins from the same county
        recipients = CustomUser.objects.filter(
            county=county,
            role__in=["Admin", "CountyOfficial"]
        )

        # Create notifications
        for user in recipients.distinct():
            Notification.objects.create(
                recipient=user,
                actor=reporter,
                verb="submitted a new report",
                description=f"New report in {county.name}: '{instance.title}'",
                target_report=instance,
            )


# ============================================================
#   COMMENT CREATED — Notify Report Owner & Officials
# ============================================================
@receiver(post_save, sender=Comment)
def notify_on_new_comment(sender, instance, created, **kwargs):
    """
    When a new comment is posted on a report:
    → Notify report owner (if not same user)
    → Notify county officials linked to the report
    """
    if created:
        report = instance.report
        commenter = instance.user

        # Get officials/admins from same county
        recipients = CustomUser.objects.filter(
            county=report.county,
            role__in=["CountyOfficial", "Admin"]
        )

        # Add the report creator (if not the same person)
        if report.created_by != commenter:
            recipients = recipients | CustomUser.objects.filter(id=report.created_by.id)

        # Send notifications
        for user in recipients.distinct():
            Notification.objects.create(
                recipient=user,
                actor=commenter,
                verb="commented on your report",
                description=f"{commenter.get_full_name()} commented on '{report.title}'",
                target_report=report,
            )
