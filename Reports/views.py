from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
import requests
from openai import OpenAI

from .models import Report
from .serializers import ReportSerializer, ReportStatusUpdateSerializer
from Authentication.models import CustomUser
from Location.models import County
from Departments.models import Department
from .utils import classify_department


# ============================================================
#   CONFIGURE OPENAI CLIENT
# ============================================================
client = OpenAI(api_key=settings.OPENAI_API_KEY)


# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================

class IsAuthenticatedAndHasRole(permissions.BasePermission):
    """Allows only authenticated users with specific roles."""
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
    """Allows deletion only by the reporter, admin, or superadmin."""
    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        return obj.reporter == request.user


class CanUpdateStatus(permissions.BasePermission):
    """Allows report status updates only for officials/admins."""
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in [
            CustomUser.Roles.COUNTY_OFFICIAL,
            CustomUser.Roles.ADMIN,
            CustomUser.Roles.SUPERADMIN,
        ]


# ============================================================
#   REPORT VIEWSET (AI + GEOLOCATION)
# ============================================================

class ReportViewSet(viewsets.ModelViewSet):
    queryset = Report.objects.all().select_related(
        "reporter", "county", "subcounty", "ward", "department"
    )
    serializer_class = ReportSerializer
    permission_classes = [IsAuthenticatedAndHasRole]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]

    filterset_fields = ["status", "county", "department", "verified_by_ai", "reporter"]
    search_fields = ["title", "description", "county__name", "department__department__name"]
    ordering_fields = ["created_at", "updated_at", "ai_confidence", "status"]
    ordering = ["-created_at"]

    # ------------------------------------------------------------
    #   CUSTOM QUERYSET BY ROLE
    # ------------------------------------------------------------
    def get_queryset(self):
        user = self.request.user

        if user.is_superadmin or user.is_admin:
            return self.queryset

        if user.is_county_official:
            return self.queryset.filter(county=user.county)

        return self.queryset.filter(reporter=user)

    # ------------------------------------------------------------
    #   CREATE REPORT (AI + LOCATION)
    # ------------------------------------------------------------
    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        # Auto-detect location
        lat = data.get("latitude")
        lon = data.get("longitude")

        if not lat or not lon:
            ip = request.META.get("REMOTE_ADDR", "")
            if ip in ("127.0.0.1", "localhost"):
                ip = "105.163.1.1"  # default Kenyan IP for local dev

            try:
                resp = requests.get(f"https://ipapi.co/{ip}/json/")
                if resp.status_code == 200:
                    geo = resp.json()
                    lat, lon = geo.get("latitude"), geo.get("longitude")
                    data["latitude"], data["longitude"] = lat, lon

                    county_name = geo.get("region")
                    if county_name:
                        county = County.objects.filter(name__icontains=county_name).first()
                        if county:
                            data["county"] = county.id
            except Exception as e:
                print(f"Location lookup failed: {e}")

        # AI classification (from utils.py)
        ai_result = classify_department(data.get("title", ""), data.get("description", ""))

        data["verified_by_ai"] = ai_result.get("verified", False)
        data["ai_confidence"] = ai_result.get("confidence", 0.0)

        # Match predicted department
        dept_name = ai_result.get("predicted_department")
        if dept_name:
            dept = Department.objects.filter(name__icontains=dept_name).first()
            if dept:
                data["department"] = dept.id

        # Optionally match predicted county
        county_name = ai_result.get("predicted_county")
        if county_name:
            county = County.objects.filter(name__icontains=county_name).first()
            if county:
                data["county"] = county.id

        # Save report
        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(reporter=request.user, role_at_submission=request.user.role)

        return Response(serializer.data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------
    #   DELETE (Soft Delete)
    # ------------------------------------------------------------
    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        if not IsReporterOrAdmin().has_object_permission(request, self, instance):
            return Response(
                {"detail": "You are not allowed to delete this report."},
                status=status.HTTP_403_FORBIDDEN,
            )
        instance.soft_delete(user=request.user)
        return Response({"detail": "Report deleted successfully."}, status=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------
    #   PATCH: /reports/{id}/status/
    # ------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="status", permission_classes=[CanUpdateStatus])
    def update_status(self, request, pk=None):
        report = self.get_object()
        serializer = ReportStatusUpdateSerializer(report, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({"detail": f"Status updated to '{report.status}'."}, status=status.HTTP_200_OK)

    # ------------------------------------------------------------
    #   PATCH: /reports/{id}/verify/
    # ------------------------------------------------------------
    @action(detail=True, methods=["patch"], url_path="verify", permission_classes=[CanUpdateStatus])
    def mark_verified(self, request, pk=None):
        report = self.get_object()
        confidence = request.data.get("ai_confidence")
        report.mark_verified(confidence=confidence)
        return Response({"detail": "Report marked as verified by AI."}, status=status.HTTP_200_OK)
