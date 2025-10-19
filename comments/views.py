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
    
    # ======================================================
    #   LIST / FILTER COMMENTS
    # ======================================================
    def get_queryset(self):
        queryset = super().get_queryset()

        report_id = self.request.query_params.get("report")
        comment_type = self.request.query_params.get("comment_type")

        if report_id:
            queryset = queryset.filter(report_id=report_id)
        if comment_type in ["citizen", "official"]:
            queryset = queryset.filter(comment_type=comment_type)

        return queryset
    
 # ======================================================
    #   CREATE COMMENT
    # ======================================================
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Ensure the related report exists and is active
        report_id = serializer.validated_data.get("report").id
        report = get_object_or_404(Report, id=report_id)

        # Only verified and active users can comment
        if not request.user.is_active or not request.user.verified:
            return Response(
                {"detail": "Please verify your account to comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    # ======================================================
    #   DELETE COMMENT
    # ======================================================
    def destroy(self, request, *args, **kwargs):
        comment = self.get_object()

        # Check custom delete permission
        if not comment.can_delete(request.user):
            return Response(
                {"detail": "You do not have permission to delete this comment."},
                status=status.HTTP_403_FORBIDDEN,
            )

        comment.is_deleted = True
        comment.save(update_fields=["is_deleted"])
        return Response(
            {"detail": "Comment deleted successfully."},
            status=status.HTTP_204_NO_CONTENT,
        )