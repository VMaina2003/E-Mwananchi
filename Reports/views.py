# Reports/views.py - COMPLETELY REWRITTEN AND OPTIMIZED
import logging
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags
from django.db import models
from django.utils import timezone
from django.db import transaction
from datetime import timedelta

from .models import Report, ReportImage, GovernmentDevelopment, ReportStatusChoices
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
            request.user and
            request.user.is_authenticated and
            request.user.role in self.allowed_roles
        )


class IsReporterOrOfficial(permissions.BasePermission):
    """Allows editing by reporter or county officials/admins."""
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        if request.user.is_county_official and obj.county == request.user.county:
            return True
        return obj.reporter == request.user


class CanUpdateStatus(permissions.BasePermission):
    """Allows report status updates by officials/admins only."""
    
    def has_permission(self, request, view):
        return (
            request.user.is_authenticated and
            request.user.role in [
                CustomUser.Roles.COUNTY_OFFICIAL,
                CustomUser.Roles.ADMIN,
                CustomUser.Roles.SUPERADMIN,
            ]
        )


# ============================================================
# REPORT VIEWSET - COMPLETELY REWRITTEN
# ============================================================
class ReportViewSet(viewsets.ModelViewSet):
    """
    Comprehensive ViewSet for report operations with AI classification,
    Cloudinary image handling, and optimized queries.
    """
    
    queryset = Report.objects.all().select_related(
        "reporter", "county", "subcounty", "ward", 
        "department", "department__department"
    ).prefetch_related(
        "images", "likes"
    ).order_by("-created_at")
    
    permission_classes = [IsAuthenticatedAndHasRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = {
        "status": ["exact", "in"],
        "county": ["exact"],
        "department": ["exact"],
        "verified_by_ai": ["exact"],
        "priority": ["exact"],
        "is_anonymous": ["exact"],
        "created_at": ["gte", "lte", "exact"],
    }
    search_fields = [
        "title", "description", 
        "county__name", "department__department__name",
        "reporter__first_name", "reporter__last_name"
    ]
    ordering_fields = [
        "created_at", "updated_at", "ai_confidence", 
        "status", "likes_count", "views_count", "priority"
    ]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        serializer_map = {
            'list': ReportListSerializer,
            'retrieve': ReportDetailSerializer,
            'update_status': ReportStatusUpdateSerializer,
            'upload_images': ReportImageUploadSerializer,
            'create': ReportSerializer,
            'update': ReportSerializer,
            'partial_update': ReportSerializer,
        }
        return serializer_map.get(self.action, ReportSerializer)

    def get_queryset(self):
        """
        Filter queryset based on user role and permissions with optimized queries.
        """
        user = self.request.user
        queryset = super().get_queryset()

        # Handle my_reports filter
        my_reports = self.request.query_params.get('my_reports', '').lower() == 'true'
        reporter_id = self.request.query_params.get('reporter')

        if my_reports:
            return queryset.filter(reporter=user)
        if reporter_id:
            return queryset.filter(reporter_id=reporter_id)

        # Apply role-based filtering
        if user.is_superadmin or user.is_admin:
            return queryset
        elif user.is_county_official:
            if user.county:
                return queryset.filter(county=user.county)
            return queryset
        else:
            # Citizens and viewers see all reports but with limited fields
            return queryset

    def get_permissions(self):
        """
        Apply specific permissions based on action.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndHasRole, IsReporterOrOfficial]
        elif self.action in ['update_status']:
            permission_classes = [IsAuthenticatedAndHasRole, CanUpdateStatus]
        else:
            permission_classes = [IsAuthenticatedAndHasRole]
        
        return [permission() for permission in permission_classes]

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new report with AI classification and image upload.
        """
        logger.info(f"Report creation initiated by user: {request.user.email}")
        
        # Prepare data for processing
        data = request.data.copy()
        images = request.FILES.getlist('new_images') or request.FILES.getlist('images')
        
        logger.info(f"Received {len(images)} images for report creation")

        # Process location data
        self._process_location_data(data)
        
        # Perform AI classification
        ai_result = self._perform_ai_classification(data)
        self._apply_ai_results(data, ai_result)

        # Validate and create report
        serializer = self.get_serializer(data=data, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                # Create report instance
                report = serializer.save(reporter=request.user)
                logger.info(f"Report created successfully: {report.id}")

                # Handle image uploads
                if images:
                    self._upload_report_images(report, images)
                    report.image_required_passed = True
                    report.save(update_fields=["image_required_passed"])
                    logger.info(f"Uploaded {len(images)} images for report {report.id}")

                # Post-creation actions
                self._handle_post_creation_actions(request, report, ai_result)

        except Exception as e:
            logger.error(f"Report creation failed: {str(e)}")
            return Response(
                {"detail": "Failed to create report. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        # Return detailed report data
        return Response(
            ReportDetailSerializer(report, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    def retrieve(self, request, *args, **kwargs):
        """Retrieve report with view count increment."""
        instance = self.get_object()
        instance.increment_views()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    # ============================================================
    # CUSTOM ACTIONS
    # ============================================================
    
    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedAndHasRole])
    def like(self, request, pk=None):
        """Like a report."""
        report = self.get_object()
        if report.like(request.user):
            return Response({
                "detail": "Report liked successfully.",
                "likes_count": report.likes_count
            })
        return Response(
            {"detail": "Report already liked."},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'], permission_classes=[IsAuthenticatedAndHasRole])
    def unlike(self, request, pk=None):
        """Unlike a report."""
        report = self.get_object()
        if report.unlike(request.user):
            return Response({
                "detail": "Report unliked successfully.",
                "likes_count": report.likes_count
            })
        return Response(
            {"detail": "Report not liked."},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticatedAndHasRole])
    def likes(self, request, pk=None):
        """Get users who liked this report."""
        report = self.get_object()
        from Authentication.serializers import UserMinimalSerializer
        likes = report.likes.all().only('id', 'first_name', 'last_name', 'email')
        serializer = UserMinimalSerializer(likes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticatedAndHasRole])
    def my_reports(self, request):
        """Get current user's reports with pagination."""
        queryset = self.get_queryset().filter(reporter=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
            
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[CanUpdateStatus])
    def update_status(self, request, pk=None):
        """Update report status with validation."""
        report = self.get_object()
        
        serializer = ReportStatusUpdateSerializer(
            report, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        updated_report = serializer.save()
        logger.info(f"Report {report.id} status updated to: {updated_report.status}")
        
        return Response(ReportDetailSerializer(updated_report).data)

    @action(detail=True, methods=['post'], permission_classes=[IsReporterOrOfficial])
    def upload_images(self, request, pk=None):
        """Upload additional images to an existing report."""
        report = self.get_object()
        images = request.FILES.getlist('images')
        
        if not images:
            return Response(
                {"detail": "No images provided."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check image limit
        current_count = report.images.count()
        if current_count + len(images) > 10:
            return Response(
                {"detail": f"Cannot upload {len(images)} images. Maximum 10 images allowed per report."},
                status=status.HTTP_400_BAD_REQUEST
            )

        uploaded_images = []
        for image_file in images:
            report_image = ReportImage.objects.create(
                report=report,
                image=image_file,
                caption=request.data.get('caption', f'Image {current_count + len(uploaded_images) + 1}')
            )
            uploaded_images.append(report_image)

        # Update image flag if needed
        if not report.image_required_passed:
            report.image_required_passed = True
            report.save(update_fields=["image_required_passed"])

        from .serializers import ReportImageSerializer
        serializer = ReportImageSerializer(uploaded_images, many=True)
        
        return Response({
            "detail": f"Successfully uploaded {len(uploaded_images)} images.",
            "images": serializer.data
        }, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get comprehensive report statistics."""
        user = request.user
        queryset = self.filter_queryset(self.get_queryset())

        try:
            # Basic counts
            stats_data = {
                "total_reports": queryset.count(),
                "verified_reports": queryset.filter(verified_by_ai=True).count(),
                "pending_reports": queryset.filter(status='pending').count(),
                "resolved_reports": queryset.filter(status='resolved').count(),
                "rejected_reports": queryset.filter(status='rejected').count(),
                "reports_with_images": queryset.filter(image_required_passed=True).count(),
                "ai_verified_reports": queryset.filter(verified_by_ai=True).count(),
                "user_reports_count": queryset.filter(reporter=user).count(),
                "user_resolved_reports": queryset.filter(reporter=user, status='resolved').count(),
                "recent_reports_count": queryset.filter(
                    created_at__gte=timezone.now() - timedelta(days=7)
                ).count(),
                "today_reports_count": queryset.filter(
                    created_at__date=timezone.now().date()
                ).count(),
            }

            # Status distribution
            stats_data["reports_by_status"] = {
                status_choice[0]: queryset.filter(status=status_choice[0]).count()
                for status_choice in ReportStatusChoices.choices
            }

            # County distribution
            if user.is_superadmin or user.is_admin or (user.is_county_official and not user.county):
                county_data = queryset.values('county__name').annotate(
                    count=models.Count('id')
                ).order_by('-count')
                stats_data["reports_by_county"] = {
                    item['county__name']: item['count'] 
                    for item in county_data if item['county__name']
                }
            elif user.is_county_official and user.county:
                stats_data["reports_by_county"] = {
                    user.county.name: queryset.filter(county=user.county).count()
                }

            # Department distribution
            dept_data = queryset.values('department__department__name').annotate(
                count=models.Count('id')
            ).order_by('-count')
            stats_data["reports_by_department"] = {
                item['department__department__name']: item['count']
                for item in dept_data if item['department__department__name']
            }

            # Engagement metrics
            stats_data.update({
                "total_likes": queryset.aggregate(total=models.Sum('likes_count'))['total'] or 0,
                "total_comments": queryset.aggregate(total=models.Sum('comments_count'))['total'] or 0,
                "total_views": queryset.aggregate(total=models.Sum('views_count'))['total'] or 0,
            })

            # Average engagement score
            total_reports = stats_data["total_reports"]
            if total_reports > 0:
                total_engagement = (
                    stats_data["total_likes"] * 2 + 
                    stats_data["total_comments"] * 3 + 
                    stats_data["total_views"] * 0.1
                )
                stats_data["average_engagement_score"] = round(total_engagement / total_reports, 2)
            else:
                stats_data["average_engagement_score"] = 0.0

            serializer = ReportStatsSerializer(stats_data)
            return Response(serializer.data)

        except Exception as e:
            logger.error(f"Statistics generation failed: {str(e)}")
            return Response(
                {"detail": "Failed to generate statistics."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # ============================================================
    # PRIVATE HELPER METHODS
    # ============================================================
    
    def _process_location_data(self, data):
        """Enrich location data with administrative boundaries."""
        lat, lon = data.get("latitude"), data.get("longitude")
        if not lat or not lon:
            return

        try:
            # Find nearest ward for location enrichment
            ward = Ward.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).extra(
                where=["POW(latitude - %s, 2) + POW(longitude - %s, 2) < 0.01"],
                params=[float(lat), float(lon)]
            ).select_related('subcounty', 'subcounty__county').first()

            if ward:
                data.update({
                    "ward": ward.id,
                    "subcounty": ward.subcounty.id,
                    "county": ward.subcounty.county.id
                })
                logger.info(f"Location enriched: {ward.subcounty.county.name}")
                
        except Exception as e:
            logger.warning(f"Location enrichment failed: {e}")

    def _perform_ai_classification(self, data):
        """Perform AI classification on report content."""
        known_departments = list(
            CountyDepartment.objects.values_list('department__name', flat=True).distinct()
        )

        try:
            return classify_department(
                data.get("title", ""),
                data.get("description", ""),
                known_departments
            )
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            return {
                "verified": False,
                "confidence": 0.0,
                "predicted_department": None,
                "predicted_county": None,
            }

    def _apply_ai_results(self, data, ai_result):
        """Apply AI classification results to report data."""
        confidence_threshold = 0.6
        ai_confidence = ai_result.get("confidence", 0.0)
        
        data.update({
            "verified_by_ai": ai_result.get("verified", False) and ai_confidence >= confidence_threshold,
            "ai_confidence": ai_confidence,
        })

        # Assign department from AI prediction
        dept_name = ai_result.get("predicted_department")
        if dept_name:
            dept = CountyDepartment.objects.filter(
                department__name__iexact=dept_name
            ).first()
            if dept:
                data["department"] = dept.id
                logger.info(f"AI assigned department: {dept_name}")

        # Assign county from AI prediction
        county_name = ai_result.get("predicted_county")
        if county_name and not data.get("county"):
            county = County.objects.filter(name__icontains=county_name.strip()).first()
            if county:
                data["county"] = county.id
                logger.info(f"AI assigned county: {county_name}")

    def _upload_report_images(self, report, images):
        """Upload images to Cloudinary and create ReportImage instances."""
        for image_file in images:
            try:
                ReportImage.objects.create(
                    report=report,
                    image=image_file,
                    caption=f"Evidence for {report.title}"
                )
            except Exception as e:
                logger.error(f"Failed to upload image {image_file.name}: {e}")
                # Continue with other images

    def _handle_post_creation_actions(self, request, report, ai_result):
        """Handle notifications and emails after report creation."""
        # Auto-verify if AI confidence is high
        if report.verified_by_ai and ai_result.get("confidence", 0) >= 0.6:
            report.status = ReportStatusChoices.VERIFIED
            report.save(update_fields=["status"])

        # Send confirmation email
        self._send_confirmation_email(request, report)
        
        # Create notification
        self._create_reporter_notification(request, report)
        
        # Notify county officials
        if report.county:
            self._notify_county_officials(report)

    def _send_confirmation_email(self, request, report):
        """Send report submission confirmation email."""
        try:
            subject = f"Report Submitted Successfully: #{report.id}"
            context = {
                'user': request.user,
                'report': report,
                'report_url': request.build_absolute_uri(f'/reports/{report.id}/'),
            }
            
            html_message = render_to_string('emails/report_submitted.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email],
                html_message=html_message,
                fail_silently=True,
            )
        except Exception as e:
            logger.error(f"Confirmation email failed: {e}")

    def _create_reporter_notification(self, request, report):
        """Create in-app notification for the reporter."""
        try:
            create_notification(
                recipient=request.user,
                actor=request.user,
                verb="submitted a report",
                description=f"Your report '{report.title}' has been submitted successfully.",
                target_report=report,
            )
        except Exception as e:
            logger.error(f"Reporter notification failed: {e}")

    def _notify_county_officials(self, report):
        """Notify relevant county officials about the new report."""
        try:
            notify_county_officials(report.county, report)
        except Exception as e:
            logger.error(f"County official notification failed: {e}")


# ============================================================
# GOVERNMENT DEVELOPMENT VIEWSET
# ============================================================
class GovernmentDevelopmentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing government development projects.
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
        """Filter queryset based on user permissions."""
        user = self.request.user
        queryset = super().get_queryset()

        if user.is_superadmin or user.is_admin:
            return queryset
        elif user.is_county_official:
            if user.county:
                return queryset.filter(county=user.county)
            return queryset
        else:
            # Citizens see only active and completed projects
            return queryset.filter(status__in=["in_progress", "completed"])

    def get_permissions(self):
        """Apply create permissions for government projects."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndHasRole]
            # Additional role checks are handled in the methods
        else:
            permission_classes = [IsAuthenticatedAndHasRole]
        
        return [permission() for permission in permission_classes]

    def create(self, request, *args, **kwargs):
        """Create a new government development project."""
        if not (request.user.is_superadmin or request.user.is_admin or request.user.is_county_official):
            return Response(
                {"detail": "Insufficient permissions to create government projects."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        data["created_by"] = request.user.id
        
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        
        development = serializer.save()
        logger.info(f"Government project created: {development.title}")
        
        return Response(
            GovernmentDevelopmentSerializer(development).data,
            status=status.HTTP_201_CREATED
        )

    @action(detail=True, methods=['post'])
    def update_progress(self, request, pk=None):
        """Update project progress with authorization checks."""
        development = self.get_object()
        
        # Authorization check
        if not self._can_modify_project(request.user, development):
            return Response(
                {"detail": "Insufficient permissions to modify this project."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = GovernmentDevelopmentProgressSerializer(
            development,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        
        updated_development = serializer.save()
        logger.info(f"Project {development.id} progress updated to {updated_development.progress_percentage}%")
        
        return Response(GovernmentDevelopmentSerializer(updated_development).data)

    @action(detail=True, methods=['post'])
    def like(self, request, pk=None):
        """Like a government development project."""
        development = self.get_object()
        if development.like(request.user):
            return Response({
                "detail": "Project liked successfully.",
                "likes_count": development.likes_count
            })
        return Response(
            {"detail": "Project already liked."},
            status=status.HTTP_400_BAD_REQUEST
        )

    @action(detail=True, methods=['post'])
    def unlike(self, request, pk=None):
        """Unlike a government development project."""
        development = self.get_object()
        if development.unlike(request.user):
            return Response({
                "detail": "Project unliked successfully.",
                "likes_count": development.likes_count
            })
        return Response(
            {"detail": "Project not liked."},
            status=status.HTTP_400_BAD_REQUEST
        )


    @action(detail=True, methods=['post'])
    def increment_views(self, request, pk=None):
        """Increment view count once per user session"""
        report = self.get_object()
        user = request.user
        
        # Use session to track views to prevent duplicates
        session_key = f'report_viewed_{report.id}'
        if not request.session.get(session_key):
            report.views_count += 1
            report.save(update_fields=['views_count'])
            request.session[session_key] = True
            request.session.modified = True
        
        return Response({'views_count': report.views_count})

    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get government development statistics."""
        user = request.user
        queryset = self.filter_queryset(self.get_queryset())

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
                "county_in_progress_projects": county_queryset.filter(status="in_progress").count(),
            })

        return Response(stats)

    def _can_modify_project(self, user, project):
        """Check if user can modify the project."""
        return (
            user.is_superadmin or
            user.is_admin or
            (user.is_county_official and user.county == project.county)
        )