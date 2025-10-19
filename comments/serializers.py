from rest_framework import serializers
from django.utils import timezone
from .models import Comment


class CommentSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()
    replies = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = [
            "id",
            "report",
            "user",
            "user_name",
            "user_role",
            "comment_type",
            "content",
            "parent",
            "replies",
            "is_deleted",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "user",
            "user_name",
            "user_role",
            "created_at",
            "updated_at",
            "is_deleted",
        ]


    # ============================
    # Custom display fields
    # ============================

    def get_user_name(self, obj):
        return obj.user.get_full_name() or obj.user.email

    def get_user_role(self, obj):
        return obj.user.role

    def get_replies(self, obj):
        """Show nested replies (optional for frontend tree view)."""
        replies = obj.replies.filter(is_deleted=False)
        return CommentSerializer(replies, many=True).data

    # ============================
    # Validation
    # ============================

    def validate(self, attrs):
        user = self.context["request"].user
        comment_type = attrs.get("comment_type")

        # Only Admins, SuperAdmins, and County Officials can post official comments
        if (
            comment_type == Comment.CommentType.OFFICIAL
            and not (user.is_admin or user.is_superadmin or user.is_county_official)
        ):
            raise serializers.ValidationError(
                "Only authorized officials can post in the official comment section."
            )

        return attrs

    # ============================
    # Create method
    # ============================

    def create(self, validated_data):
        user = self.context["request"].user
        validated_data["user"] = user
        comment = Comment.objects.create(**validated_data)
        return comment