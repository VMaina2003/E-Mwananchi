from rest_framework import viewsets, permissions, status, filters
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
from django.conf import settings
import openai
import requests

from .models import Report
from .serializers import ReportSerializer, ReportStatusUpdateSerializer
from Authentication.models import CustomUser
from Location.models import County
from Departments.models import Department


# ============================================================
#   CONFIGURE OPENAI
# ============================================================
openai.api_key = settings.OPENAI_API_KEY


def ai_analyze_report(title, description):
    """
    Sends the report data to OpenAI for:
    - Verification (real/genuine or spam)
    - Department classification
    - Confidence scoring
    """
    prompt = f"""
    You are an assistant verifying public service reports in Kenya.
    A citizen has submitted a report.

    Title: {title}
    Description: {description}

    Task:
    1. Determine if this is a genuine issue that should be reported.
    2. Suggest the most appropriate county department (e.g., Health, Roads, Education, Environment, Water, Trade, ICT, Finance, Housing, Agriculture).
    3. Give a confidence score (0 to 1).

    Respond strictly in JSON format:
    {{
        "verified": true/false,
        "confidence": float between 0 and 1,
        "predicted_department": "Department Name"
    }}
    """

    try:
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a civic issue classification model."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=200,
            temperature=0.2,
        )

        import json
        ai_text = response.choices[0].message.content.strip()
        result = json.loads(ai_text)
        return result

    except Exception as e:
        print(f"⚠️ AI classification failed: {e}")
        return {
            "verified": False,
            "confidence": 0.0,
            "predicted_department": None,
        }


# ============================================================
#   PERMISSIONS (same as before)
# ============================================================

class IsAuthenticatedAndHasRole(permissions.BasePermission):
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
    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        return obj.reporter == request.user


class CanUpdateStatus(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in [
            CustomUser.Roles.COUNTY_OFFICIAL,
            CustomUser.Roles.ADMIN,
            CustomUser.Roles.SUPERADMIN,
        ]


# ============================================================
#   REPORT VIEWSET (AI + Geolocation)
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

    def create(self, request, *args, **kwargs):
        data = request.data.copy()

        # 🗺️ Auto-detect location
        lat = data.get("latitude")
        lon = data.get("longitude")

        if not lat or not lon:
            ip = request.META.get('REMOTE_ADDR', '')
            if ip in ('127.0.0.1', 'localhost'):
                ip = "105.163.1.1"
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
                print(f"⚠️ Location detection failed: {e}")

        # 🤖 AI Verification
        ai_result = ai_analyze_report(data.get("title", ""), data.get("description", ""))

        data["verified_by_ai"] = ai_result.get("verified", False)
        data["ai_confidence"] = ai_result.get("confidence", 0.0)

        # Assign Department Automatically
        dept_name = ai_result.get("predicted_department")
        if dept_name:
            dept = Department.objects.filter(name__icontains=dept_name).first()
            if dept:
                data["department"] = dept.id

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            reporter=request.user,
            role_at_submission=request.user.role,
        )

        return Response(serializer.data, status=status.HTTP_201_CREATED)
