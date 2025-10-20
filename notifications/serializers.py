from rest_framework import serializers
from .models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    report_title = serializers.SerializerMethodField()

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
            "target_report",
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
            "target_report",
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
        """Return the title of the related report."""
        return obj.target_report.title if obj.target_report else None


class NotificationUpdateSerializer(serializers.ModelSerializer):
    """Serializer used for marking notifications as read/unread."""

    class Meta:
        model = Notification
        fields = ["is_read"]
