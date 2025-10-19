from django.contrib import admin
from .models import Comment


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    """
    Custom admin panel for viewing and managing comments.
    """

    list_display = (
        "id",
        "report",
        "user",
        "comment_type",
        "short_content",
        "is_deleted",
        "created_at",
    )
    list_filter = ("comment_type", "is_deleted", "created_at")
    search_fields = ("content", "user__email", "user__first_name", "report__title")
    readonly_fields = ("created_at", "updated_at")
    ordering = ("-created_at",)
    autocomplete_fields = ("report", "user", "parent")

    def short_content(self, obj):
        """Display only a snippet of the comment for readability."""
        return (obj.content[:50] + "...") if len(obj.content) > 50 else obj.content

    short_content.short_description = "Comment"
