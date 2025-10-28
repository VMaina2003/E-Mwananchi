from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    report_title = serializers.SerializerMethodField()
    
    # Custom field to display the related report's ID (assuming 'target' is the GFK)
    target_id = serializers.ReadOnlyField(source='target.id') 

    class Meta:
        model = Notification
        fields = [
            "id",
            "recipient",
            "actor",
            "actor_name",
            "verb",
            "description",
            "report_title",
             
            "target_id",
            "is_read",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "recipient",
            "actor",
            "actor_name",
            "verb",
            "description",
            "report_title",
             
            "target_id",
            "created_at",
        ]

    # ==========================================================
    # Custom Fields
    # ==========================================================

    def get_actor_name(self, obj):
        """Return full name or email of the actor."""
        if obj.actor:
            return obj.actor.get_full_name() or obj.actor.email
        return None

    def get_report_title(self, obj):
        """Return the title of the related report, assuming 'target' is the Report instance."""
        #  Check if target exists AND if it has a 'title' attribute (i.e., it's a Report)
        if obj.target and hasattr(obj.target, 'title'):
            return obj.target.title 
        return None


class NotificationUpdateSerializer(serializers.ModelSerializer):
    """Serializer used for marking notifications as read/unread."""

    class Meta:
        model = Notification
        fields = ["is_read"]