from rest_framework import serializers
from django.utils import timezone
from .models import Report, ReportImage, ReportStatusChoices
from Location.models import County, SubCounty, Ward
from Departments.models import CountyDepartment


# ============================================================
#   REPORT IMAGE SERIALIZER
# ============================================================
class ReportImageSerializer(serializers.ModelSerializer):
    """Handles image upload and retrieval for reports."""

    class Meta:
        model = ReportImage
        fields = ["id", "image", "caption", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


# ============================================================
#   REPORT SERIALIZER (MAIN)
# ============================================================
class ReportSerializer(serializers.ModelSerializer):
    """
    Serializes report data for creation, retrieval, and update.

    - Automatically attaches the reporter and role.
    - Validates presence of title, description, and image.
    - Handles nested image uploads.
    """

    # Include related images (nested)
    images = ReportImageSerializer(many=True, read_only=True)
    new_images = serializers.ListField(
        child=serializers.ImageField(max_length=None, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
        help_text="Attach one or more images to this report."
    )
    
    # Read-only fields for display
    reporter_name = serializers.CharField(source="reporter.get_full_name", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)
    department_name = serializers.CharField(source="department.department.name", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "description",
            "reporter",
            "reporter_name",
            "role_at_submission",
            "county",
            "county_name",
            "subcounty",
            "ward",
            "latitude",
            "longitude",
            "department",
            "department_name",
            "status",
            "verified_by_ai",
            "ai_confidence",
            "image_required_passed",
            "created_at",
            "updated_at",
            "images",
            "new_images",
        ]
        read_only_fields = [
            "id",
            "reporter",
            "role_at_submission",
            "verified_by_ai",
            "ai_confidence",
            "image_required_passed",
            "created_at",
            "updated_at",
        ]