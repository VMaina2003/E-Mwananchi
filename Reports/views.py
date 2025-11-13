# Reports/views.py - UPDATED
import logging
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.core.mail import send_mail 
from django.template.loader import render_to_string 
from django.utils.html import strip_tags 
import requests

from .models import Report, ReportImage, GovernmentDevelopment
from .serializers import (
    ReportSerializer, 
    ReportStatusUpdateSerializer,
    ReportListSerializer,
    ReportDetailSerializer,
    ReportImageUploadSerializer,
    ReportStatsSerializer,
    GovernmentDevelopmentSerializer,
    GovernmentDevelopmentProgressSerializer
)
from Authentication.models import CustomUser
from Location.models import County, SubCounty, Ward
from Departments.models import CountyDepartment
from Reports.utils import classify_department
from notifications.utils import create_notification, notify_county_officials 
from django.db import models  

logger = logging.getLogger(__name__)

# ============================================================
# CUSTOM PERMISSIONS 
# ============================================================
class IsAuthenticatedAndHasRole(permissions.BasePermission):
    """Allows only authenticated users with valid roles."""
    allowed_roles = [
        CustomUser.Roles.CITIZEN,
        CustomUser.Roles.VIEWER,
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
    """Allows editing/deletion by reporter or admin."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        return obj.reporter == request.user


class CanUpdateStatus(permissions.BasePermission):
    """Allows report status updates by officials/admins only."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in [
            CustomUser.Roles.COUNTY_OFFICIAL,
            CustomUser.Roles.ADMIN,
            CustomUser.Roles.SUPERADMIN,
        ]


class CanUploadImages(permissions.BasePermission):
    """Allows image uploads by reporter or admin."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        return obj.reporter == request.user


# ============================================================
# REPORT VIEWSET - FIXED FOR BROWSE VS MY REPORTS
# ============================================================
class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling report operations with AI classification and notifications.
    """
    queryset = Report.objects.all().select_related(
        "reporter", "county", "subcounty", "ward", "department", "department__department"
    ).prefetch_related("images", "likes")
    permission_classes = [IsAuthenticatedAndHasRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "county", "department", "verified_by_ai"]
    search_fields = ["title", "description", "county__name", "department__department__name"]
    ordering_fields = ["created_at", "updated_at", "ai_confidence", "status", "likes_count", "views_count"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """
        Return appropriate serializer based on action.
        """
        if self.action == 'list':
            return ReportListSerializer
        elif self.action == 'retrieve':
            return ReportDetailSerializer
        elif self.action == 'update_status':
            return ReportStatusUpdateSerializer
        elif self.action == 'upload_images':
            return ReportImageUploadSerializer
        return ReportSerializer

    def get_queryset(self):
        """
        Filter queryset based on user role and permissions.
        FIXED: Browse Reports shows ALL reports, My Reports shows user's reports only
        """
        user = self.request.user
        queryset = self.queryset

        # Check if this is a "my_reports" request
        my_reports = self.request.query_params.get('my_reports', 'false').lower() == 'true'
        reporter_filter = self.request.query_params.get('reporter')

        if my_reports or reporter_filter:
            # For "My Reports" or specific reporter filter - show only user's reports
            if reporter_filter:
                return queryset.filter(reporter_id=reporter_filter)
            else:
                return queryset.filter(reporter=user)
        
        # For Browse Reports - show ALL reports based on user permissions
        if user.is_superadmin or user.is_admin:
            return queryset
        elif user.is_county_official:
            # County officials can see reports from their assigned county OR all counties if no county assigned
            if user.county:
                logger.info(f"County official {user.email} accessing reports for assigned county: {user.county.name}")
                return queryset.filter(county=user.county)
            else:
                # Allow county officials without assigned counties to see all reports
                logger.info(f"County official {user.email} without assigned county accessing all reports")
                return queryset
        else:
            # Citizens and viewers can see ALL reports (not just their own) for browsing
            logger.info(f"User {user.email} accessing all reports for browsing")
            return queryset

    # ------------------------------------------------------------
    # LIST ACTION (Optimized for performance)
    # ------------------------------------------------------------
    def list(self, request, *args, **kwargs):
        """
        Optimized list endpoint using lightweight serializer.
        """
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # ------------------------------------------------------------
    # CREATE REPORT (ENHANCED AI + NOTIFICATIONS)
    # ------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        """
        Create a new report with AI classification and notifications.
        """
        data = request.data.copy()
        logger.info(f"Creating new report for user: {request.user.email}")

        # --- 1. Geolocation extraction (no fallback) ---
        lat, lon = data.get("latitude"), data.get("longitude")
        if not lat or not lon:
            # If no coordinates provided, don't auto-fill - let user input manually
            logger.info("No GPS coordinates provided - user will input location manually")
        else:
            # If coordinates provided, try to enrich with location data
            self._enrich_location_data(data, lat, lon)

        # --- 2. AI Classification ---
        ai_result = self._perform_ai_classification(data)
        
        # --- 3. Assign AI results with confidence threshold ---
        confidence_threshold = 0.6
        ai_confidence = ai_result.get("confidence", 0.0)
        data["verified_by_ai"] = ai_result.get("verified", False) and ai_confidence >= confidence_threshold
        data["ai_confidence"] = ai_confidence

        # --- 4. Department Assignment ---
        self._assign_department_from_ai(data, ai_result)
        
        # --- 5. County Assignment ---
        self._assign_county_from_ai(data, ai_result)

        # --- 6. Validate and Create Report ---
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        report = serializer.save(reporter=request.user)

        # --- 7. Post-Creation Processing ---
        self._handle_post_creation_actions(request, report, ai_confidence)
        
        return Response(ReportDetailSerializer(report).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------
    # CUSTOM ACTIONS - ADD LIKE/UNLIKE FUNCTIONALITY
    # ------------------------------------------------------------
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedAndHasRole])
    def like(self, request, pk=None):
        """
        Like a report.
        """
        report = self.get_object()
        if report.like(request.user):
            return Response({
                "detail": "Report liked successfully.", 
                "likes_count": report.likes_count
            })
        return Response({"detail": "Report already liked."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedAndHasRole])
    def unlike(self, request, pk=None):
        """
        Unlike a report.
        """
        report = self.get_object()
        if report.unlike(request.user):
            return Response({
                "detail": "Report unliked successfully.", 
                "likes_count": report.likes_count
            })
        return Response({"detail": "Report not liked."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedAndHasRole])
    def increment_views(self, request, pk=None):
        """
        Increment report view count.
        """
        report = self.get_object()
        report.increment_views()
        return Response({
            "detail": "View count incremented.", 
            "views_count": report.views_count
        })

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedAndHasRole])
    def likes(self, request, pk=None):
        """
        Get users who liked this report.
        """
        report = self.get_object()
        likes = report.likes.all()
        from Authentication.serializers import UserSerializer
        serializer = UserSerializer(likes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndHasRole])
    def my_reports(self, request):
        """
        Get only the current user's reports.
        """
        queryset = self.get_queryset().filter(reporter=request.user)
        queryset = self.filter_queryset(queryset)
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # ------------------------------------------------------------
    # EXISTING METHODS (keep the same)
    # ------------------------------------------------------------
    @action(detail=True, methods=['post'], permission_classes=[CanUpdateStatus])
    def update_status(self, request, pk=None):
        """
        Custom endpoint for updating report status.
        """
        report = self.get_object()
        
        # Additional permission check for county officials without assigned counties
        if request.user.is_county_official and not request.user.county:
            logger.info(f"County official {request.user.email} without assigned county updating report {report.id} status")
            # Allow status updates for any report since they can access all reports
        
        serializer = self.get_serializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        updated_report = serializer.save()
        
        logger.info(f"Report {report.id} status updated to: {updated_report.status}")
        return Response(ReportDetailSerializer(updated_report).data)

    @action(detail=True, methods=['post'], permission_classes=[CanUploadImages])
    def upload_images(self, request, pk=None):
        """
        Upload images to an existing report.
        """
        report = self.get_object()
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Add report context for the serializer
        serializer.context['report_id'] = report.id
        image = serializer.save()
        
        # Update image_required_passed flag
        if not report.image_required_passed:
            report.image_required_passed = True
            report.save(update_fields=["image_required_passed"])
        
        logger.info(f"Image uploaded to report {report.id}")
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get report statistics for dashboards.
        """
        user = request.user
        queryset = self.get_queryset()
        
        # Basic stats
        total_reports = queryset.count()
        verified_reports = queryset.filter(verified_by_ai=True).count()
        pending_reports = queryset.filter(status='pending').count()
        rejected_reports = queryset.filter(status='rejected').count()
        reports_with_images = queryset.filter(image_required_passed=True).count()
        ai_verified_reports = queryset.filter(verified_by_ai=True).count()
        
        # User-specific stats
        user_reports_count = queryset.filter(reporter=user).count()
        user_resolved_reports = queryset.filter(reporter=user, status='resolved').count()
        
        # Status distribution
        reports_by_status = dict(queryset.values_list('status').annotate(count=models.Count('id')))
        
        # County distribution (for admins/officials)
        reports_by_county = {}
        if user.is_superadmin or user.is_admin or (user.is_county_official and not user.county):
            # Show county distribution for admins and county officials without assigned counties
            reports_by_county = dict(queryset.values_list('county__name').annotate(count=models.Count('id')))
        elif user.is_county_official and user.county:
            # For county officials with assigned counties, only show their county
            reports_by_county = {user.county.name: queryset.filter(county=user.county).count()}
        
        # Department distribution
        reports_by_department = dict(
            queryset.values_list('department__department__name').annotate(count=models.Count('id'))
        )
        
        # Recent reports (last 7 days)
        from django.utils import timezone
        from datetime import timedelta
        recent_reports_count = queryset.filter(
            created_at__gte=timezone.now() - timedelta(days=7)
        ).count()
        
        # County-specific stats for officials
        county_specific_stats = {}
        if user.is_county_official and user.county:
            county_queryset = queryset.filter(county=user.county)
            county_specific_stats = {
                "assigned_county": user.county.name,
                "county_total_reports": county_queryset.count(),
                "county_verified_reports": county_queryset.filter(verified_by_ai=True).count(),
                "county_resolved_reports": county_queryset.filter(status='resolved').count(),
            }
        elif user.is_county_official and not user.county:
            county_specific_stats = {
                "assigned_county": None,
                "access_level": "multi_county",
                "total_counties_accessed": len(reports_by_county)
            }
        
        stats_data = {
            "total_reports": total_reports,
            "verified_reports": verified_reports,
            "pending_reports": pending_reports,
            "rejected_reports": rejected_reports,
            "reports_with_images": reports_with_images,
            "ai_verified_reports": ai_verified_reports,
            "user_reports_count": user_reports_count,
            "user_resolved_reports": user_resolved_reports,
            "reports_by_status": reports_by_status,
            "reports_by_county": reports_by_county,
            "reports_by_department": reports_by_department,
            "recent_reports_count": recent_reports_count,
            **county_specific_stats
        }
        
        serializer = ReportStatsSerializer(stats_data)
        return Response(serializer.data)

    # ------------------------------------------------------------
    # PRIVATE HELPER METHODS (keep the same)
    # ------------------------------------------------------------
    def _enrich_location_data(self, data, lat, lon):
        """Try to enrich location data with county, subcounty, ward information."""
        try:
            logger.info(f"Attempting to enrich location data for coordinates: {lat}, {lon}")
            
            # First, try to find the exact ward
            ward = Ward.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).extra(
                where=[
                    "POW(latitude - %s, 2) + POW(longitude - %s, 2) < 0.01"  # ~1km radius
                ],
                params=[float(lat), float(lon)]
            ).select_related('subcounty', 'subcounty__county').first()
            
            if ward:
                logger.info(f"Found ward: {ward.name} in {ward.subcounty.county.name}")
                data["ward"] = ward.id
                data["subcounty"] = ward.subcounty.id
                data["county"] = ward.subcounty.county.id
                return
            
            # If no ward found, try to find by county proximity
            # This is a simplified approach - in production you'd use a proper geocoding service
            logger.info("No precise ward found - user will need to select location manually")
            
        except Exception as e:
            logger.warning(f"Location enrichment failed: {e}")

    def _perform_ai_classification(self, data):
        """Perform AI classification on report data."""
        known_departments = list(
            CountyDepartment.objects.values_list('department__name', flat=True).distinct()
        )
        logger.info(f"Available departments for AI classification: {known_departments}")

        try:
            ai_result = classify_department(
                data.get("title", ""), 
                data.get("description", ""), 
                known_departments
            )
            logger.info(f"AI Classification Result: {ai_result}")
            return ai_result
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return {
                "verified": False,
                "confidence": 0.0,
                "predicted_department": None,
                "predicted_county": None,
            }

    def _assign_department_from_ai(self, data, ai_result):
        """Assign department based on AI prediction."""
        dept_name = ai_result.get("predicted_department")
        if dept_name:
            logger.info(f"AI predicted department: {dept_name}")
            dept = (
                CountyDepartment.objects.filter(department__name__iexact=dept_name).first() or
                CountyDepartment.objects.filter(department__name__icontains=dept_name).first() or
                CountyDepartment.objects.first()  # Fallback
            )
            if dept:
                data["department"] = dept.id
                logger.info(f"Successfully assigned department: {dept.department.name}")
            elif "department" in data:
                del data["department"]
                logger.info("No department match found, removing department assignment")

    def _assign_county_from_ai(self, data, ai_result):
        """Assign county based on AI prediction."""
        county_name = ai_result.get("predicted_county")
        if county_name:
            logger.info(f"AI predicted county: {county_name}")
            county = County.objects.filter(name__icontains=county_name.strip()).first()
            if county:
                data["county"] = county.id
                logger.info(f"Auto-assigned county from AI: {county.name}")
            elif "county" in data and not data.get("county"):
                del data["county"]

    def _handle_status_update(self, request, instance):
        """Handle report status updates."""
        self.permission_classes = [CanUpdateStatus] 
        self.check_permissions(request)
        
        status_serializer = ReportStatusUpdateSerializer(
            instance, data={'status': request.data['status']}, partial=True
        )
        status_serializer.is_valid(raise_exception=True)
        updated_instance = status_serializer.save()
        
        logger.info(f"Report status updated to: {updated_instance.status}")
        return Response(ReportDetailSerializer(updated_instance).data)

    def _handle_post_creation_actions(self, request, report, ai_confidence):
        """Handle actions after report creation."""
        # Auto-update status if AI verified
        if report.verified_by_ai and ai_confidence >= 0.6:
            report.status = "verified"
            report.save(update_fields=["status"])
            logger.info(f"Report auto-verified by AI with {ai_confidence} confidence")

        # Send confirmation email
        self._send_confirmation_email(request, report)
        
        # Create in-app notification for reporter
        self._create_reporter_notification(request, report)
        
        # Notify county officials
        if report.county:
            self._notify_county_officials(report)

    def _send_confirmation_email(self, request, report):
        """Send confirmation email to reporter."""
        try:
            subject = f"Report Submitted Successfully: #{report.id}"
            context = {
                'user': request.user,
                'report': report,
                'report_url': request.build_absolute_uri(f'/reports/{report.id}/'), 
            }
            
            html_message = render_to_string('report_submitted_confirmation.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email], 
                html_message=html_message,
                fail_silently=True,
            )
            logger.info(f"Confirmation email sent to {request.user.email}")
        except Exception as e:
            logger.error(f"Failed to send confirmation email: {e}")

    def _create_reporter_notification(self, request, report):
        """Create in-app notification for reporter."""
        try:
            create_notification(
                recipient=request.user,
                actor=request.user,
                verb="submitted a report",
                description=f"Your report '{report.title}' has been successfully submitted.",
                target_report=report,
            )
            logger.info("Created notification for reporter")
        except Exception as e:
            logger.error(f"Failed to create reporter notification: {e}")

    def _notify_county_officials(self, report):
        """Notify county officials about new report."""
        try:
            notify_county_officials(report.county, report)
            logger.info(f"Notified county officials for {report.county.name}")
        except Exception as e:
            logger.error(f"Failed to notify county officials: {e}")

# ============================================================
# GOVERNMENT DEVELOPMENT VIEWSET (keep the same)
# ============================================================
class GovernmentDevelopmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for handling government development projects.
    """
    queryset = GovernmentDevelopment.objects.all().select_related(
        "county", "department", "department__department", "created_by"
    ).prefetch_related("images", "likes")
    serializer_class = GovernmentDevelopmentSerializer
    permission_classes = [IsAuthenticatedAndHasRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "county", "department"]
    search_fields = ["title", "description", "county__name", "department__department__name"]
    ordering_fields = ["created_at", "updated_at", "progress_percentage", "start_date"]
    ordering = ["-created_at"]

    def get_queryset(self):
        """
        Filter queryset based on user permissions.
        """
        user = self.request.user
        queryset = self.queryset

        # Admins and superadmins can see all projects
        if user.is_superadmin or user.is_admin:
            return queryset
        
        # County officials can see projects from their assigned county OR all counties if no county assigned
        elif user.is_county_official:
            if user.county:
                return queryset.filter(county=user.county)
            else:
                return queryset
        
        # Citizens and viewers can see all active projects
        else:
            return queryset.filter(status__in=["planned", "in_progress", "completed"])

    def create(self, request, *args, **kwargs):
        """
        Create a new government development project.
        Only admins and county officials can create projects.
        """
        if not (request.user.is_superadmin or request.user.is_admin or request.user.is_county_official):
            return Response(
                {"detail": "You don't have permission to create government projects."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        data["created_by"] = request.user.id
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        development = serializer.save()
        
        logger.info(f"Government development project created: {development.title}")
        return Response(GovernmentDevelopmentSerializer(development).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """
        Update project progress percentage and status.
        """
        development = self.get_object()
        
        # Check permissions
        if not (request.user.is_superadmin or request.user.is_admin or 
                (request.user.is_county_official and request.user.county == development.county)):
            return Response(
                {"detail": "You don't have permission to update this project."},
                status=status.HTTP_403_FORBIDDEN
            )

        progress_percentage = request.data.get('progress_percentage')
        update_text = request.data.get('progress_updates')
        
        try:
            development.update_progress(progress_percentage, update_text)
            logger.info(f"Project {development.id} progress updated to {progress_percentage}%")
            return Response(GovernmentDevelopmentSerializer(development).data)
        except ValidationError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """
        Like a government development project.
        """
        development = self.get_object()
        if development.like(request.user):
            return Response({"detail": "Project liked successfully.", "likes_count": development.likes_count})
        return Response({"detail": "Project already liked."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def unlike(self, request, pk=None):
        """
        Unlike a government development project.
        """
        development = self.get_object()
        if development.unlike(request.user):
            return Response({"detail": "Project unliked successfully.", "likes_count": development.likes_count})
        return Response({"detail": "Project not liked."}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['post'])
    def increment_views(self, request, pk=None):
        """
        Increment project view count.
        """
        development = self.get_object()
        development.increment_views()
        return Response({"detail": "View count incremented.", "views_count": development.views_count})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get government development statistics.
        """
        user = request.user
        queryset = self.get_queryset()
        
        stats = {
            "total_projects": queryset.count(),
            "planned_projects": queryset.filter(status="planned").count(),
            "in_progress_projects": queryset.filter(status="in_progress").count(),
            "completed_projects": queryset.filter(status="completed").count(),
            "delayed_projects": queryset.filter(status="delayed").count(),
            "total_budget": float(queryset.aggregate(total=models.Sum('budget'))['total'] or 0),
            "average_progress": queryset.aggregate(avg=models.Avg('progress_percentage'))['avg'] or 0,
        }
        
        # County-specific stats for officials
        if user.is_county_official and user.county:
            county_queryset = queryset.filter(county=user.county)
            stats.update({
                "county_total_projects": county_queryset.count(),
                "county_budget": float(county_queryset.aggregate(total=models.Sum('budget'))['total'] or 0),
                "county_completed_projects": county_queryset.filter(status="completed").count(),
            })
        
        return Response(stats)