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
    - Validates required fields.
    - Handles nested image uploads.
    """

    # Nested images
    images = ReportImageSerializer(many=True, read_only=True)
    new_images = serializers.ListField(
        child=serializers.ImageField(max_length=None, allow_empty_file=False, use_url=False),
        write_only=True,
        required=False,
        help_text="Attach one or more images to this report."
    )

    # Read-only display fields
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

    # --------------------------------------------------------
    #   VALIDATION LOGIC
    # --------------------------------------------------------
    def validate(self, data):
        """Ensure title, description, and county are provided."""
        if not data.get("title"):
            raise serializers.ValidationError("A report must have a title.")
        if not data.get("description"):
            raise serializers.ValidationError("Please provide a detailed description.")
        if not data.get("county"):
            raise serializers.ValidationError("County is required.")
        return data

    # --------------------------------------------------------
    #   CREATE METHOD (FIXED VERSION)
    # --------------------------------------------------------
    def create(self, validated_data):
        """
        Custom create method:
        - Attaches the reporter and role.
        - Handles image uploads.
        """
        # Extract images if provided
        new_images = validated_data.pop("new_images", [])
        
        # Get reporter from context (set by the view)
        reporter = self.context['request'].user
        
        # Create the report with reporter and role
        report = Report.objects.create(
            reporter=reporter,
            role_at_submission=reporter.role,
            **validated_data
        )
        
        # Handle image uploads
        if new_images:
            for image_file in new_images:
                ReportImage.objects.create(report=report, image=image_file)
            report.image_required_passed = True
            report.save(update_fields=["image_required_passed"])

        return report

    # --------------------------------------------------------
    #   UPDATE METHOD
    # --------------------------------------------------------
    def update(self, instance, validated_data):
        """
        Custom update method:
        - Restricts editing based on status.
        - Updates only allowed fields.
        """
        if not instance.is_editable_by_reporter():
            raise serializers.ValidationError("You cannot edit this report after verification.")

        allowed_fields = ["title", "description", "county", "subcounty", "ward"]
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)

        instance.updated_at = timezone.now()
        instance.save()
        return instance


# ============================================================
#   REPORT STATUS UPDATE SERIALIZER
# ============================================================
class ReportStatusUpdateSerializer(serializers.ModelSerializer):
    """
    Used by officials, admins, or superadmins to update the status of a report.
    """

    class Meta:
        model = Report
        fields = ["status"]

    def validate_status(self, value):
        """Ensure provided status is valid."""
        valid_choices = [choice[0] for choice in ReportStatusChoices.choices]
        if value not in valid_choices:
            raise serializers.ValidationError(f"Invalid status '{value}'.")
        return value

    def update(self, instance, validated_data):
        new_status = validated_data["status"]
        instance.mark_status(new_status)
        return instance