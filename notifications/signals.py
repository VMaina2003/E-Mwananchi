from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Notification
from Reports.models import Report
from comments.models import Comment

# ===============================================
#   REPORT CREATED — Notify Admins/Officials
# ===============================================
@receiver(post_save, sender=Report)
def notify_on_new_report(sender, instance, created, **kwargs):
    """
    When a new report is submitted by a citizen:
    → Notify all admins and county officials in that county.
    """
    if created:
        county = instance.county
        reporter = instance.created_by

        from Authentication.models import CustomUser
        recipients = CustomUser.objects.filter(
            county=county, role__in=["Admin", "CountyOfficial"]
        )

        for user in recipients:
            Notification.objects.create(
                recipient=user,
                actor=reporter,
                verb="submitted a new report",
                message=f"New report in {county.name}: {instance.title}",
                target_type="report",
                target_id=instance.id,
            )


# ===============================================
#   COMMENT CREATED — Notify Report Owner & Officials
# ===============================================
@receiver(post_save, sender=Comment)
def notify_on_new_comment(sender, instance, created, **kwargs):
    """
    When a new comment is posted on a report:
    → Notify report owner (if not the same user)
    → Notify county officials linked to the report
    """
    if created:
        report = instance.report
        commenter = instance.user

        from Authentication.models import CustomUser
        recipients = CustomUser.objects.filter(
            county=report.county, role__in=["CountyOfficial", "Admin"]
        )

        # Notify report creator (if not the one commenting)
        if report.created_by != commenter:
            recipients = recipients | CustomUser.objects.filter(id=report.created_by.id)

        # Send notification
        for user in recipients.distinct():
            Notification.objects.create(
                recipient=user,
                actor=commenter,
                verb="commented on",
                message=f"{commenter.get_full_name()} commented on your report '{report.title}'",
                target_type="comment",
                target_id=instance.id,
            )
