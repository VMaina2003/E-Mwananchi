from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404

from .models import Comment
from .serializers import CommentSerializer
from Reports.models import Report


# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================

class CanDeleteComment(permissions.BasePermission):
    """
    Custom permission to allow deletion only by:
    - the comment owner
    - admins / superadmins
    - county officials
    """

    def has_object_permission(self, request, view, obj):
        user = request.user
        return obj.can_delete(user)
    
# ============================================================
#   COMMENT VIEWSET
# ============================================================

class CommentViewSet(viewsets.ModelViewSet):
    """
    Handles creating, listing, and deleting comments.
    Supports citizen and official comment sections.
    """

    queryset = Comment.objects.filter(is_deleted=False).select_related("user", "report")
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["content", "user__email", "user__first_name"]
    ordering_fields = ["created_at"]