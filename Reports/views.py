from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from .models import Report, ReportImage, ReportStatusChoices
from .serializers import ReportSerializer, ReportStatusUpdateSerializer
from Authentication.models import CustomUser
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters

# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================
class IsAuthenticatedAndHasRole(permissions.BasePermission):
    """
    Allows access only to authenticated users with allowed roles.
    """

    allowed_roles = [
        CustomUser.Roles.CITIZEN,
        CustomUser.Roles.COUNTY_OFFICIAL,
        CustomUser.Roles.ADMIN,
        CustomUser.Roles.SUPERADMIN,
    ]

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsReporterOrAdmin(permissions.BasePermission):
    """
    Allows a report to be edited/deleted only by:
    - The creator (reporter)
    - Admin or Superadmin
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        return obj.reporter == request.user


class CanUpdateStatus(permissions.BasePermission):
    """
    Allows report status updates only for:
    - County Officials
    - Admins
    - Superadmins
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in [
            CustomUser.Roles.COUNTY_OFFICIAL,
            CustomUser.Roles.ADMIN,
            CustomUser.Roles.SUPERADMIN,
        ]


# ============================================================
#   REPORT VIEWSET
# ============================================================
class ReportViewSet(viewsets.ModelViewSet):
    """
    Handles all CRUD operations for Reports.
    - Citizens can create and view their own reports.
    - County officials, admins, and superadmins can view all reports.
    - Reporters can edit before verification.
    """

    queryset = Report.objects.all().select_related(
        "reporter", "county", "subcounty", "ward", "department"
    )
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticatedAndHasRole]
    
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    #  Filter by specific fields
    filterset_fields = [
        "status",
        "county",
        "department",
        "verified_by_ai",
        "reporter",
    ]

    #  Allow text search
    search_fields = [
        "title",
        "description",
        "county__name",
        "subcounty__name",
        "ward__name",
        "department__department__name",
    ]

    #  Allow ordering
    ordering_fields = ["created_at", "updated_at", "ai_confidence", "status"]
    ordering = ["-created_at"]  # default ordering
    
    
    def get_queryset(self):
        """Filter reports based on user role."""
        user = self.request.user

        if user.is_superadmin or user.is_admin:
            return self.queryset  # View all reports

        if user.is_county_official:
            # View only reports from their county (simplified)
            return self.queryset.filter(county__name__iexact=user.last_name)  # <-- adjust if you link official to county

        # Citizen sees only their reports
        return self.queryset.filter(reporter=user)

    def perform_create(self, serializer):
        """Auto-attach reporter and their role at submission."""
        serializer.save(reporter=self.request.user, role_at_submission=self.request.user.role)

    def destroy(self, request, *args, **kwargs):
        """Soft delete only (creator, admin, superadmin)."""
        instance = self.get_object()
        if not IsReporterOrAdmin().has_object_permission(request, self, instance):
            return Response(
                {"detail": "You are not allowed to delete this report."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.soft_delete(user=request.user)
        return Response({"detail": "Report deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------
    #   EXTRA ENDPOINT: /reports/{id}/status/
    # ------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="status", permission_classes=[CanUpdateStatus])
    def update_status(self, request, pk=None):
        """
        Used by officials/admins to update the report status.
        Example:
            PATCH /api/reports/{id}/status/
            { "status": "on_progress" }
        """
        report = self.get_object()
        serializer = ReportStatusUpdateSerializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": f"Status updated to '{report.status}'."}, status=status.HTTP_200_OK)

    # ------------------------------------------------------------
    #   EXTRA ENDPOINT: /reports/{id}/verify/
    # ------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="verify", permission_classes=[CanUpdateStatus])
    def mark_verified(self, request, pk=None):
        """
        Used when AI or admin marks report as verified.
        Example:
            PATCH /api/reports/{id}/verify/
            { "ai_confidence": 0.88 }
        """
        report = self.get_object()
        confidence = request.data.get("ai_confidence")
        report.mark_verified(confidence=confidence)
        return Response({"detail": "Report marked as verified by AI."}, status=status.HTTP_200_OK)