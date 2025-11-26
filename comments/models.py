# models.py - UPDATED COMMENT MODEL
import uuid
from django.db import models
from django.conf import settings
from django.utils import timezone
from Reports.models import Report

class Comment(models.Model):
    class CommentType(models.TextChoices):
        CITIZEN = "citizen", "Citizen Comment"
        OFFICIAL = "official", "Official Response"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    report = models.ForeignKey(
        Report, 
        on_delete=models.CASCADE, 
        related_name="comments"  # Changed to simpler name
    )
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name="comments"
    )
    
    comment_type = models.CharField(
        max_length=20, choices=CommentType.choices, default=CommentType.CITIZEN
    )
    content = models.TextField()
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    
    # Control and timestamps
    is_deleted = models.BooleanField(default=False)
    is_approved = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=['report', 'comment_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
        ]

    def __str__(self):
        return f"{self.comment_type} by {self.user.email} on {self.report.title}"

    def save(self, *args, **kwargs):
        if not self.user_id:
            raise ValueError("User must be set for comment")
        super().save(*args, **kwargs)

    # FIXED METHODS WITH PROPER USER ATTRIBUTE CHECKING
    def get_user_display_name(self):
        """Get appropriate display name for the commenter."""
        if hasattr(self.user, 'first_name') and hasattr(self.user, 'last_name'):
            if self.user.first_name and self.user.last_name:
                return f"{self.user.first_name} {self.user.last_name}"
            elif self.user.first_name:
                return self.user.first_name
        
        # Fallback to email username
        if hasattr(self.user, 'email'):
            return self.user.email.split('@')[0]
        return "Anonymous"

    def can_edit(self, user):
        """Check if user can edit this comment."""
        if not user or not user.is_authenticated:
            return False
        
        # Users can edit their own comments within 15 minutes
        if self.user_id == user.id:
            time_since_creation = timezone.now() - self.created_at
            return time_since_creation.total_seconds() <= 900  # 15 minutes
        
        # Check if user has special permissions
        if hasattr(user, 'is_admin') and user.is_admin:
            return True
        if hasattr(user, 'is_superadmin') and user.is_superadmin:
            return True
        if hasattr(user, 'is_county_official') and user.is_county_official:
            return True
            
        return False

    def can_delete(self, user):
        """Check if user can delete this comment."""
        if not user or not user.is_authenticated:
            return False
        
        # Comment owner can always delete their own comments
        if self.user_id == user.id:
            return True
        
        # Check if user has special permissions
        if hasattr(user, 'is_admin') and user.is_admin:
            return True
        if hasattr(user, 'is_superadmin') and user.is_superadmin:
            return True
        if hasattr(user, 'is_county_official') and user.is_county_official:
            return True
            
        return False

    @property
    def reply_count(self):
        """Count of non-deleted replies."""
        return self.replies.filter(is_deleted=False, is_approved=True).count()