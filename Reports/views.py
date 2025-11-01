from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
from django.core.mail import send_mail 
from django.template.loader import render_to_string 
from django.utils.html import strip_tags 
import requests

# Assuming these models and utility functions are defined and accessible
from .models import Report
from .serializers import ReportSerializer, ReportStatusUpdateSerializer 
from Authentication.models import CustomUser
from Location.models import County
from Departments.models import CountyDepartment
from Reports.utils import classify_department
# Import notification utility functions from your notifications app
from notifications.utils import create_notification, notify_county_officials 

# ============================================================
# CUSTOM PERMISSIONS 
# ============================================================
class IsAuthenticatedAndHasRole(permissions.BasePermission):
    """Allows only authenticated users with valid roles."""
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


# ============================================================
# REPORT VIEWSET
# ============================================================
class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all().select_related(
        "reporter", "county", "subcounty", "ward", "department"
    )
    # NOTE: ReportSerializer MUST have the 'reporter' field defined as read_only=True
    serializer_class = ReportSerializer 
    permission_classes = [IsAuthenticatedAndHasRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ["status", "county", "department", "verified_by_ai", "reporter"]
    search_fields = ["title", "description", "county__name", "department__department__name"]
    ordering_fields = ["created_at", "updated_at", "ai_confidence", "status"]
    ordering = ["-created_at"]

    def get_queryset(self):
        user = self.request.user
        if user.is_superadmin or user.is_admin:
            return self.queryset
        if user.is_county_official:
            return self.queryset.filter(county=user.county)
        return self.queryset.filter(reporter=user)

    # ------------------------------------------------------------
    # CREATE REPORT (AI + NOTIFICATIONS)
    # ------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        # --- 1. Geolocation fallback (Existing logic)
        lat, lon = data.get("latitude"), data.get("longitude")
        if not lat or not lon:
            ip = request.META.get("REMOTE_ADDR", "105.163.1.1") 
            try:
                resp = requests.get(f"https://ipapi.co/{ip}/json/")
                if resp.status_code == 200:
                    geo = resp.json()
                    lat, lon = geo.get("latitude"), geo.get("longitude")
                    
                    if lat and lon:
                        data["latitude"], data["longitude"] = lat, lon

                    county_name = geo.get("region")
                    if county_name and not data.get("county"):
                        county = County.objects.filter(name__icontains=county_name).first()
                        if county:
                            data["county"] = county.id
            except Exception as e:
                print(f"Location lookup failed: {e}")

        # --- 2. AI Classification (Existing logic)
        known_departments = list(CountyDepartment.objects.values_list('department__name', flat=True).distinct())
        ai_result = classify_department(
            data.get("title", ""), 
            data.get("description", ""), 
            known_departments
        )
        
        # --- 3. Assign AI results
        data["verified_by_ai"] = ai_result.get("verified", False)
        data["ai_confidence"] = ai_result.get("confidence", None)

        # --- 4. & 5. Safe Department & County assignment (Existing logic)
        dept_name = ai_result.get("predicted_department")
        if dept_name:
            dept_qs = CountyDepartment.objects.filter(department__name__icontains=dept_name.strip())
            dept = dept_qs.first()
            if dept:
                data["department"] = dept.id
            elif "department" in data:
                del data["department"]
            
        county_name = ai_result.get("predicted_county")
        if county_name:
            county = County.objects.filter(name__icontains=county_name.strip()).first()
            if county:
                data["county"] = county.id
            elif "county" in data:
                del data["county"]
            
        # IMPORTANT: Do NOT include 'reporter' in the initial data passed to the serializer 
        # when using a read_only PrimaryKeyRelatedField, as it can cause conflicts.
        # data['reporter'] = request.user.id # <-- DELETE THIS LINE

       # --- 6. Validate Data
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)

            # FIX: Pass the request context to serializer
        serializer.context['request'] = request

            # Create report - reporter is handled in serializer via context
        report = serializer.save()
        # --- 7. Automatically mark status as verified
        if ai_result.get("verified", False):
            report.status = "verified"
            report.save(update_fields=["status"])

        # --- 8A. 📧 Email Confirmation to the Reporter
        try:
            subject = f"Report Submitted Successfully: #{report.id}"
            context = {
                'user': request.user,
                'report': report,
                'report_url': request.build_absolute_uri(f'/reports/{report.id}/'), 
            }
            
            # Corrected template path based on your file structure (notifications/templates/)
            html_message = render_to_string('report_submitted_confirmation.html', context)
            plain_message = strip_tags(html_message)
            
            send_mail(
                subject,
                plain_message,
                settings.DEFAULT_FROM_EMAIL,
                [request.user.email], 
                html_message=html_message,
                fail_silently=False,
            )
            
        except Exception as e:
            print(f"ERROR: Failed to send report submission email to {request.user.email}. Error: {e}")

        # --- 8B. 🔔 In-App Notification for Reporter
        try:
            create_notification(
        recipient=request.user,
        actor=request.user,
        verb="submitted a report",
        # DELETE this line: target=report, 
        description=f"Your report '{report.title}' has been successfully submitted.",
)
        except Exception as e:
            print(f"ERROR: Failed to create confirmation notification for reporter. Error: {e}")
            
        # --- 8C. 🔔 Notifications for County Officials
        if report.county:
            try:
                notify_county_officials(report.county, report)
            except Exception as e:
                print(f"ERROR: Failed to notify county officials for report {report.id}. Error: {e}")

        return Response(ReportSerializer(report).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------
    # OTHER ACTIONS (UPDATE, DELETE)
    # ------------------------------------------------------------
    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        
        # Check for status update attempts
        if 'status' in request.data:
            self.check_permissions(request)
            self.permission_classes = [CanUpdateStatus] 
            
            status_serializer = ReportStatusUpdateSerializer(
                instance, data={'status': request.data['status']}, partial=True
            )
            status_serializer.is_valid(raise_exception=True)
            status_serializer.save()
            return Response(ReportSerializer(instance).data)

        # Handle standard report updates (title, description, location)
        if not instance.is_editable_by_reporter():
            return Response(
                {"detail": "This report cannot be edited after verification."},
                status=status.HTTP_403_FORBIDDEN
            )

        # Use the standard serializer for allowed field updates
        self.check_object_permissions(request, instance)
        serializer = self.get_serializer(instance, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)