from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

from .models import Comment
from .serializers import CommentSerializer, CommentCreateSerializer, CommentUpdateSerializer
from Reports.models import Report


# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================

class CanDeleteComment(permissions.BasePermission):
    """Custom permission to allow deletion only by authorized users."""
    
    def has_object_permission(self, request, view, obj):
        return obj.can_delete(request.user)

class CanEditComment(permissions.BasePermission):
    """Custom permission to allow editing only by comment owner within time limit."""
    
    def has_object_permission(self, request, view, obj):
        return obj.can_edit(request.user)

class IsOfficialOrReadOnly(permissions.BasePermission):
    """Allow officials to post official comments, citizens to post citizen comments."""
    
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        
        if request.method == 'POST':
            comment_type = request.data.get('comment_type', 'citizen')
            if comment_type == 'official':
                return request.user.is_authenticated and (
                    request.user.is_county_official or 
                    request.user.is_admin or 
                    request.user.is_superadmin
                )
        return True


# ============================================================
#   COMMENT VIEWSET
# ============================================================

class CommentViewSet(viewsets.ModelViewSet):
    """
    Handles creating, listing, and managing comments.
    Supports citizen comments and official responses.
    """

    queryset = Comment.objects.filter(
        is_deleted=False, 
        is_approved=True
    ).select_related("user", "report", "parent")
    
    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticatedOrReadOnly, IsOfficialOrReadOnly]
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["content", "user__first_name", "user__last_name"]
    ordering_fields = ["created_at", "updated_at"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        if self.action == 'create':
            return CommentCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return CommentUpdateSerializer
        return CommentSerializer

    def get_permissions(self):
        if self.action in ['update', 'partial_update']:
            return [permissions.IsAuthenticated(), CanEditComment()]
        elif self.action == 'destroy':
            return [permissions.IsAuthenticated(), CanDeleteComment()]
        return super().get_permissions()

    def get_queryset(self):
        queryset = super().get_queryset()
        
        report_id = self.request.query_params.get("report")
        comment_type = self.request.query_params.get("comment_type")
        parent_id = self.request.query_params.get("parent")
        user_id = self.request.query_params.get("user")

        if report_id:
            queryset = queryset.filter(report_id=report_id)

        if comment_type in ["citizen", "official"]:
            queryset = queryset.filter(comment_type=comment_type)

        if parent_id:
            if parent_id == "null":
                queryset = queryset.filter(parent__isnull=True)
            else:
                queryset = queryset.filter(parent_id=parent_id)

        if user_id:
            queryset = queryset.filter(user_id=user_id)

        return queryset

    def perform_create(self, serializer):
        """Automatically set the user when creating a comment."""
        comment = serializer.save(user=self.request.user)
        
        # Send email notification for official responses
        if comment.comment_type == 'official':
            self.send_official_response_notification(comment)

    def send_official_response_notification(self, comment):
        """Send email notification when an official response is posted."""
        try:
            report = comment.report
            subject = f"Official Response to Your Report: {report.title}"
            
            message = f"""
            Dear {report.reporter.first_name if report.reporter.first_name else 'Citizen'},
            
            An official response has been added to your report "{report.title}".
            
            Official Response:
            {comment.content}
            
            Report Details:
            - Title: {report.title}
            - Status: {report.get_status_display()}
            - Department: {report.department.department.name if report.department else 'Not assigned'}
            
            You can view the full response and report details at:
            {getattr(settings, 'FRONTEND_URL', 'http://localhost:3000')}/reports/{report.id}
            
            Thank you for using our platform to improve your community.
            
            Best regards,
            County Government Platform
            """
            
            if report.reporter and report.reporter.email:
                send_mail(
                    subject=subject,
                    message=message,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[report.reporter.email],
                    fail_silently=True,
                )
                print(f"Official response notification sent to {report.reporter.email}")
                
        except Exception as e:
            print(f"Failed to send email notification: {e}")

    def create(self, request, *args, **kwargs):
        """Simplified create method - let DRF handle the creation."""
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        # Validate comment type permissions
        comment_type = serializer.validated_data.get('comment_type', 'citizen')
        if comment_type == 'official':
            if not (request.user.is_county_official or request.user.is_admin or request.user.is_superadmin):
                return Response(
                    {"detail": "Only county officials can post official responses."},
                    status=status.HTTP_403_FORBIDDEN,
                )

        # Let DRF handle the creation (this will call perform_create automatically)
        self.perform_create(serializer)
        
        # Use the instance from the serializer to get the full comment data
        comment = serializer.instance
        
        # Return full comment data using the main serializer
        full_serializer = CommentSerializer(comment, context={"request": request})
        
        return Response(full_serializer.data, status=status.HTTP_201_CREATED)

    def destroy(self, request, *args, **kwargs):
        """Soft delete comment."""
        comment = self.get_object()

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

    @action(detail=False, methods=["get"], url_path="report/(?P<report_id>[^/.]+)")
    def get_by_report(self, request, report_id=None):
        """Get all comments for a specific report."""
        comments = self.get_queryset().filter(report_id=report_id)
        serializer = self.get_serializer(comments, many=True)
        return Response(serializer.data)