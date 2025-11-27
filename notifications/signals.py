from django.db.models.signals import post_save
from django.dispatch import receiver
from django.core.mail import EmailMultiAlternatives, send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.template.exceptions import TemplateDoesNotExist
from comments.models import Comment
from Reports.models import Report

@receiver(post_save, sender=Comment)
def notify_report_owner_on_comment(sender, instance, created, **kwargs):
    """
    When an OFFICIAL comment is made on a report, send an email notification to the report owner.
    Only send emails for official responses, not citizen comments.
    """
    if not created:
        return

    # ONLY send emails for official comments
    if instance.comment_type != Comment.CommentType.OFFICIAL:
        return

    # Check if the comment has a report relationship
    if not hasattr(instance, 'report') or not instance.report:
        return

    report = instance.report
    commenter = instance.user
    
    # Check if report has a reporter
    if not hasattr(report, 'reporter') or not report.reporter:
        return
        
    reporter = report.reporter

    # Don't email yourself if you comment on your own report
    if commenter == reporter:
        return

    # Use the correct field name 'content' instead of 'text'
    comment_content = instance.content

    # Build the report URL (adjust based on your URL structure)
    report_url = f"{getattr(settings, 'SITE_URL', 'http://localhost:3000')}/reports/{report.id}"

    # Email context
    context = {
        'reporter_name': reporter.get_full_name() or "Reporter",
        'report_title': report.title,
        'report_id': report.id,
        'commenter_name': commenter.get_full_name(),
        'commenter_email': commenter.email,
        'comment_text': comment_content,
        'report_url': report_url,
        'comment_type': instance.get_comment_type_display(),
        'department': getattr(report.department, 'department.name', 'County Government') if hasattr(report, 'department') and report.department else 'County Government',
    }

    # Subject
    subject = f" Official Response to Your Report: {report.title}"

    try:
        # Try to render the HTML template
        html_content = render_to_string('official_response_notification.html', context)
        
        # Create plain text version as fallback
        text_content = f"""
Hi {context['reporter_name']},

 OFFICIAL RESPONSE TO YOUR REPORT

Your report titled "{report.title}" has received an official response from {context['department']}.

OFFICIAL RESPONSE FROM: {commenter.get_full_name()} ({commenter.email})
RESPONSE: {comment_content}

You can view your report and the official response at: {report_url}

Thank you for your civic engagement!

Best regards,
E-Mwananchi Team
"""

        # Send HTML email
        email = EmailMultiAlternatives(
            subject,
            text_content,
            settings.DEFAULT_FROM_EMAIL,
            [reporter.email],
        )
        email.attach_alternative(html_content, "text/html")
        email.send(fail_silently=False)
        print(f" Official response notification (green theme) sent to {reporter.email}")
        
    except TemplateDoesNotExist:
        # Fallback to simple text email if template doesn't exist
        print("  Template not found, sending plain text email")
        
        simple_message = f"""
Hi {context['reporter_name']},

 OFFICIAL RESPONSE TO YOUR REPORT

Your report titled "{report.title}" has received an official response from {context['department']}.

OFFICIAL RESPONSE FROM: {commenter.get_full_name()} ({commenter.email})
RESPONSE: {comment_content}

You can view your report and the official response at: {report_url}

Thank you for your continued engagement in improving our community!

Best regards,
E-Mwananchi Team
"""
        send_mail(
            subject,
            simple_message,
            settings.DEFAULT_FROM_EMAIL,
            [reporter.email],
            fail_silently=False,
        )
        print(f"Plain text official response notification sent to {reporter.email}")
        
    except Exception as e:
        print(f" Failed to send official response notification: {e}")