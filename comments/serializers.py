# comments/serializers.py - FIXED VERSION
from rest_framework import serializers
from django.utils import timezone
from .models import Comment

class CommentSerializer(serializers.ModelSerializer):
    """Serializer for comment data with user information."""
    
    user_display_name = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()  # Changed to method field
    user_avatar = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    reply_count = serializers.SerializerMethodField()  # Changed to method field
    replies = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            "id", "report", "user", "user_display_name", "user_role", "user_avatar",
            "comment_type", "content", "parent", "is_deleted", "is_approved",
            "created_at", "updated_at", "can_edit", "can_delete", 
            "reply_count", "replies"
        ]
        read_only_fields = [
            "id", "user", "created_at", "updated_at", "user_display_name",
            "user_role", "user_avatar", "can_edit", "can_delete", "reply_count"
        ]

    def get_user_display_name(self, obj):
        """Get appropriate display name for the commenter."""
        return obj.get_user_display_name()

    def get_user_role(self, obj):
        """Safely get user role."""
        if hasattr(obj.user, 'role'):
            return obj.user.role
        return 'citizen'  # default

    def get_user_avatar(self, obj):
        """Get user avatar or generate initial-based avatar."""
        if hasattr(obj.user, 'profile_picture') and obj.user.profile_picture:
            return obj.user.profile_picture.url
        
        # Return initials for avatar
        initials = ""
        if hasattr(obj.user, 'first_name') and obj.user.first_name:
            initials += obj.user.first_name[0].upper()
        if hasattr(obj.user, 'last_name') and obj.user.last_name:
            initials += obj.user.last_name[0].upper()
        return initials if initials else "U"

    def get_can_edit(self, obj):
        """Check if current user can edit this comment."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_edit(request.user)
        return False

    def get_can_delete(self, obj):
        """Check if current user can delete this comment."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_delete(request.user)
        return False

    def get_reply_count(self, obj):
        """Get count of replies."""
        return obj.reply_count

    def get_replies(self, obj):
        """Get approved, non-deleted replies."""
        replies = obj.replies.filter(is_deleted=False, is_approved=True)
        return CommentSerializer(replies, many=True, context=self.context).data

    def validate_content(self, value):
        """Validate comment content."""
        content = value.strip()
        if len(content) < 1:
            raise serializers.ValidationError("Comment cannot be empty.")
        if len(content) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return content

class CommentCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating comments (simplified version)."""
    
    class Meta:
        model = Comment
        fields = ["report", "content", "comment_type", "parent"]

    def validate(self, data):
        """Validate comment creation."""
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("Authentication required.")
        
        # Ensure user is verified and active
        if not request.user.is_active or not request.user.verified:
            raise serializers.ValidationError("Account must be verified and active to comment.")
        
        # Validate comment type permissions
        comment_type = data.get('comment_type', 'citizen')
        if comment_type == 'official':
            if not (request.user.is_county_official or request.user.is_admin or request.user.is_superadmin):
                raise serializers.ValidationError("Only county officials can post official responses.")
        
        return data


class CommentUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating comments."""
    
    class Meta:
        model = Comment
        fields = ["content"]

    def validate_content(self, value):
        """Validate updated content."""
        content = value.strip()
        if len(content) < 1:
            raise serializers.ValidationError("Comment cannot be empty.")
        if len(content) > 1000:
            raise serializers.ValidationError("Comment cannot exceed 1000 characters.")
        return content

    def update(self, instance, validated_data):
        """Update comment with edit tracking."""
        # Check if user can still edit
        if not instance.can_edit(self.context.get('request').user):
            raise serializers.ValidationError("Comment can no longer be edited.")
        
        instance.content = validated_data['content']
        instance.save(update_fields=['content', 'updated_at'])
        return instance