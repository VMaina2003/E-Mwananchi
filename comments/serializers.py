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