from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import send_mail
from django.conf import settings
from comments.models import Comment
from Reports.models import Report

@receiver(post_save, sender=Comment)
def notify_report_owner_on_comment(sender, instance, created, **kwargs):
    """
    When a comment is made on a report, send an email notification to the report owner.
    """
    if not created:
        return

    report = instance.report
    commenter = instance.user
    reporter = report.reporter  # the citizen who created the report

    # Don’t email yourself if you comment on your own report
    if commenter == reporter:
        return

    subject = f"New Comment on Your Report: {report.title}"
    message = f"""
Hi {reporter.get_full_name()},

Your report titled "{report.title}" has received a new comment.

Commented by: {commenter.get_full_name()} ({commenter.email})
Comment: {instance.text}

You can view your report in the system for more details.

Best regards,
E-Mwananchi Team
"""

    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,   # This will use e.mwananchi254@gmail.com
        [reporter.email],
        fail_silently=False,
    )
