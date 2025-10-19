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