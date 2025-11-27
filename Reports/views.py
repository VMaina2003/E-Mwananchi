# Reports/views.py - COMPLETE FIXED VERSION WITH OFFICIAL MANAGEMENT
import logging
from rest_framework import viewsets, permissions, status, filters
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
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
    ReportCreateSerializer,
    ReportUpdateSerializer,
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
    """
    Permission class that allows report status updates by any county official,
    administrator, or super administrator.
    """
    
    def has_permission(self, request, view):
        """
        Check if user has permission to update report status.
        Allows any county official, admin, or superadmin regardless of county assignment.
        """
        return (
            request.user and
            request.user.is_authenticated and
            request.user.role in [
                CustomUser.Roles.COUNTY_OFFICIAL,
                CustomUser.Roles.ADMIN,
                CustomUser.Roles.SUPERADMIN,
            ]
        )


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
    
    parser_classes = [MultiPartParser, FormParser, JSONParser]
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
        """
        Return appropriate serializer class based on the current action.
        """
        serializer_map = {
            'list': ReportListSerializer,
            'retrieve': ReportDetailSerializer,
            'create': ReportCreateSerializer,
            'update': ReportUpdateSerializer,
            'partial_update': ReportUpdateSerializer,
            'update_status': ReportStatusUpdateSerializer,
            'upload_images': ReportImageUploadSerializer,
            'my_reports': ReportListSerializer,
            'stats': ReportStatsSerializer,
        }
        return serializer_map.get(self.action, ReportSerializer)

    def get_queryset(self):
        """
        Filter queryset based on user role and permissions.
        Provides appropriate data access based on user privileges.
        """
        user = self.request.user
        queryset = super().get_queryset()

        my_reports = self.request.query_params.get('my_reports', '').lower() == 'true'
        reporter_id = self.request.query_params.get('reporter')

        if my_reports:
            return queryset.filter(reporter=user)
        if reporter_id:
            return queryset.filter(reporter_id=reporter_id)

        if user.is_superadmin or user.is_admin:
            return queryset
        elif user.is_county_official:
            return queryset
        else:
            return queryset

    def get_permissions(self):
        """
        Apply specific permission classes based on the action being performed.
        """
        if self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [IsAuthenticatedAndHasRole, IsReporterOrOfficial]
        elif self.action in ['update_status', 'add_response', 'assign_department', 'update_priority']:
            permission_classes = [IsAuthenticatedAndHasRole, CanUpdateStatus]
        elif self.action in ['like', 'unlike']:
            permission_classes = [IsAuthenticatedAndHasRole]
        else:
            permission_classes = [IsAuthenticatedAndHasRole]
        
        return [permission() for permission in permission_classes]

    def get_serializer_context(self):
        """
        Add request object to serializer context for access in serializers.
        """
        context = super().get_serializer_context()
        context['request'] = self.request
        return context

    def can_user_manage_report(self, user, report):
        """
        Check if user has permission to manage a specific report.
        Allows any county official to manage any report regardless of county assignment.
        """
        if user.is_superadmin or user.is_admin:
            return True
        if user.is_county_official:
            return True
        return False

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        Create a new report with AI classification and image upload functionality.
        Includes comprehensive validation and error handling.
        """
        logger.info(f"Report creation initiated by user: {request.user.email}")
        
        logger.info(f"Request data keys: {list(request.data.keys())}")
        logger.info(f"Request FILES keys: {list(request.FILES.keys())}")
        
        images = request.FILES.getlist('images')
        logger.info(f"Found {len(images)} images in field 'images'")
        
        for img in images:
            logger.info(f"Image: {img.name} ({img.size} bytes, {img.content_type})")

        data = request.data.copy()
        
        data.pop('images', None)
        data.pop('new_images', None)
        
        logger.info(f"Data after cleanup: {list(data.keys())}")

        self._process_location_data(data)
        
        ai_result = self._perform_ai_classification(data)
        self._apply_ai_results(data, ai_result)

        serializer = ReportCreateSerializer(data=data, context={'request': request})
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.error(f"Serializer validation failed: {str(e)}")
            return Response(
                {"detail": "Validation failed", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                report = serializer.save()
                logger.info(f"Report created successfully: {report.id}")

                image_count = report.images.count()
                logger.info(f"Report now has {image_count} images attached")

                self._handle_post_creation_actions(request, report, ai_result)

        except Exception as e:
            logger.error(f"Report creation failed: {str(e)}")
            return Response(
                {"detail": f"Failed to create report: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        return Response(
            ReportDetailSerializer(report, context={'request': request}).data,
            status=status.HTTP_201_CREATED
        )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        Update an existing report with proper validation and permission checks.
        """
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        
        if not (instance.reporter == request.user or 
                request.user.is_superadmin or 
                request.user.is_admin or
                (request.user.is_county_official and instance.county == request.user.county)):
            return Response(
                {"detail": "You do not have permission to edit this report."},
                status=status.HTTP_403_FORBIDDEN
            )

        data = request.data.copy()
        
        data.pop('images', None)
        data.pop('new_images', None)

        serializer = ReportUpdateSerializer(
            instance, 
            data=data, 
            partial=partial,
            context={'request': request}
        )
        
        try:
            serializer.is_valid(raise_exception=True)
        except Exception as e:
            logger.error(f"Serializer validation failed during update: {str(e)}")
            return Response(
                {"detail": "Validation failed", "errors": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report = serializer.save()
        
        return Response(
            ReportDetailSerializer(report, context={'request': request}).data,
            status=status.HTTP_200_OK
        )
    def retrieve(self, request, *args, **kwargs):
        """Retrieve report with view count increment."""
        instance = self.get_object()
        instance.increment_views()
        serializer = ReportDetailSerializer(instance, context={'request': request})
        return Response(serializer.data)

    # Custom Actions
    
    @action(detail=True, methods=['post'])
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

    @action(detail=True, methods=['post'])
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

    @action(detail=True, methods=['get'])
    def likes(self, request, pk=None):
        """Get users who liked this report."""
        report = self.get_object()
        from Authentication.serializers import UserMinimalSerializer
        likes = report.likes.all().only('id', 'first_name', 'last_name', 'email')
        serializer = UserMinimalSerializer(likes, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_reports(self, request):
        """Get current user's reports with pagination."""
        queryset = self.get_queryset().filter(reporter=request.user)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = ReportListSerializer(page, many=True, context={'request': request})
            return self.get_paginated_response(serializer.data)
            
        serializer = ReportListSerializer(queryset, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def update_status(self, request, pk=None):
        """Update report status with validation."""
        report = self.get_object()
        
        # Check if user can manage this county's reports
        if not self.can_user_manage_report(request.user, report):
            return Response(
                {"detail": "You can only update reports from your assigned county."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = ReportStatusUpdateSerializer(
            report, 
            data=request.data, 
            partial=True,
            context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        
        updated_report = serializer.save()
        logger.info(f"Report {report.id} status updated to: {updated_report.status}")
        
        return Response(ReportDetailSerializer(updated_report, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def add_response(self, request, pk=None):
        """Add government response to report."""
        report = self.get_object()
        
        if not self.can_user_manage_report(request.user, report):
            return Response(
                {"detail": "You can only respond to reports from your assigned county."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        response_text = request.data.get('government_response')
        if not response_text:
            return Response(
                {"detail": "Response text is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report.add_government_response(response_text, request.user)
        return Response(ReportDetailSerializer(report, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def assign_department(self, request, pk=None):
        """Assign report to specific department."""
        report = self.get_object()
        
        if not self.can_user_manage_report(request.user, report):
            return Response(
                {"detail": "You can only assign reports from your assigned county."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        department_id = request.data.get('department')
        if not department_id:
            return Response(
                {"detail": "Department ID is required."},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            department = CountyDepartment.objects.get(id=department_id)
            report.department = department
            report.save()
            return Response(ReportDetailSerializer(report, context={'request': request}).data)
        except CountyDepartment.DoesNotExist:
            return Response(
                {"detail": "Department not found."},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def update_priority(self, request, pk=None):
        """Update report priority."""
        report = self.get_object()
        
        if not self.can_user_manage_report(request.user, report):
            return Response(
                {"detail": "You can only update priority for reports from your assigned county."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        priority = request.data.get('priority')
        valid_priorities = ['low', 'medium', 'high', 'urgent']
        
        if priority not in valid_priorities:
            return Response(
                {"detail": f"Priority must be one of: {', '.join(valid_priorities)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        report.priority = priority
        report.save()
        return Response(ReportDetailSerializer(report, context={'request': request}).data)

    @action(detail=True, methods=['post'])
    def upload_images(self, request, pk=None):
        """Upload additional images to an existing report."""
        report = self.get_object()
        
        # Check permissions
        if not (report.reporter == request.user or 
                request.user.is_superadmin or 
                request.user.is_admin or
                (request.user.is_county_official and report.county == request.user.county)):
            return Response(
                {"detail": "You do not have permission to add images to this report."},
                status=status.HTTP_403_FORBIDDEN
            )

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

    # Debug endpoint for file upload testing
    @action(detail=False, methods=['post'])
    def debug_upload(self, request):
        """Debug endpoint to check file uploads."""
        logger.info("Debug upload endpoint called")
        logger.info(f"Method: {request.method}")
        logger.info(f"Content-Type: {request.content_type}")
        logger.info(f"Data keys: {list(request.data.keys())}")
        logger.info(f"Files keys: {list(request.FILES.keys())}")
        
        files_detail = {}
        for key, files in request.FILES.lists():
            files_detail[key] = [{
                'name': f.name,
                'size': f.size,
                'content_type': f.content_type
            } for f in files]
        
        return Response({
            'data_keys': list(request.data.keys()),
            'files_keys': list(request.FILES.keys()),
            'files_detail': files_detail,
            'user': request.user.email if request.user.is_authenticated else 'Anonymous'
        })

    # Private helper methods
    
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
            logger.info("Attempting AI classification...")
            result = classify_department(
                data.get("title", ""),
                data.get("description", ""),
                known_departments
            )
            logger.info(f"AI classification result: {result}")
            return result
        except Exception as e:
            logger.error(f"AI classification failed: {e}")
            # Return fallback result
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

    def _handle_post_creation_actions(self, request, report, ai_result):
        """Handle notifications and emails after report creation."""
        # Auto-verify if AI confidence is high
        if report.verified_by_ai and ai_result.get("confidence", 0) >= 0.6:
            report.status = ReportStatusChoices.VERIFIED
            report.save(update_fields=["status"])
            logger.info(f"Report {report.id} auto-verified due to high AI confidence")

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
            
            # Try multiple template locations
            template_locations = [
                'emails/report_submitted.html',
                'Reports/emails/report_submitted.html',
            ]
            
            html_message = None
            for template in template_locations:
                try:
                    html_message = render_to_string(template, context)
                    break
                except:
                    continue
            
            if not html_message:
                # Create a simple email template if file doesn't exist
                html_message = f"""
                <html>
                <body>
                    <h2>Report Submitted Successfully</h2>
                    <p>Hello {request.user.get_full_name()},</p>
                    <p>Your report has been submitted successfully.</p>
                    <p><strong>Title:</strong> {report.title}</p>
                    <p><strong>Reference ID:</strong> #{report.id}</p>
                    <p>You can view your report at: {request.build_absolute_uri(f'/reports/{report.id}/')}</p>
                </body>
                </html>
                """
            
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
            logger.info(f"Notification created for reporter {request.user.email}")
        except Exception as e:
            logger.error(f"Reporter notification failed: {e}")

    def _notify_county_officials(self, report):
        """Notify relevant county officials about the new report."""
        try:
            notify_county_officials(report.county, report)
            logger.info(f"County officials notified for report {report.id}")
        except Exception as e:
            logger.error(f"County official notification failed: {e}")


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
        development = self.get_object()
        user = request.user
        
        # Use session to track views to prevent duplicates
        session_key = f'development_viewed_{development.id}'
        if not request.session.get(session_key):
            development.views_count += 1
            development.save(update_fields=['views_count'])
            request.session[session_key] = True
            request.session.modified = True
        
        return Response({'views_count': development.views_count})

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