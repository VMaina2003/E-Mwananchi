from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import Notification
from Reports.models import Report
from Comments.models import Comment

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

        from Users.models import CustomUser
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