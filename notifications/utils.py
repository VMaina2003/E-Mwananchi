
from .models import Notification
from Authentication.models import CustomUser
from Reports.models import Report 

# ONLY accept arguments that you plan to pass to the Notification model constructor
def create_notification(recipient, actor, verb, description=None):
    """
    Creates a new Notification instance using only fields your model supports.
    """
    
    notification = Notification.objects.create(
        recipient=recipient,
        actor=actor,
        verb=verb,
        description=description or f"{actor.get_full_name()} {verb}.",
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
        # FINAL FIX: Removed the 'target=report' argument from this call site
        create_notification(
            recipient=official,
            actor=report.reporter,
            verb=f"submitted a new report in your county: {report.title}",
            description=f"A new report (#{report.id}) has been submitted for review.",
        )