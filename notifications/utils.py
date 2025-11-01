from .models import Notification
from Authentication.models import CustomUser
from Reports.models import Report 

def create_notification(recipient, actor, verb, description=None, target_report=None):
    """
    Creates a new Notification instance.
    """
    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        description=description or f"{actor.get_full_name()} {verb}.",
        target_report=target_report,  # Use the actual field name from your model
    )
    return notification


def notify_county_officials(county, report):
    """
    Finds officials in the given county and creates a notification for each.
    """
    officials = CustomUser.objects.filter(
        county=county, 
        role=CustomUser.Roles.COUNTY_OFFICIAL
    )
    
    for official in officials:
        create_notification(
            recipient=official,
            actor=report.reporter,
            verb=f"submitted a new report in your county: {report.title}",
            description=f"A new report (#{report.id}) has been submitted for review.",
            target_report=report,  # Pass the report object
        )