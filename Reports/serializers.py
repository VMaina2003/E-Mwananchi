from rest_framework import serializers
from django.utils import timezone
from .models import Report, ReportImage, GovernmentDevelopment, ReportStatusChoices
from Authentication.models import CustomUser
from Location.models import County, SubCounty, Ward
from Departments.models import CountyDepartment


# ============================================================
#   REPORT IMAGE SERIALIZERS
# ============================================================
class ReportImageSerializer(serializers.ModelSerializer):
    """Handles image retrieval for reports."""
    
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = ReportImage
        fields = ["id", "image", "image_url", "caption", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None


class ReportImageUploadSerializer(serializers.ModelSerializer):
    """Serializer specifically for uploading images to reports."""
    
    class Meta:
        model = ReportImage
        fields = ["image", "caption"]
    
    def create(self, validated_data):
        report_id = self.context.get('report_id')
        try:
            report = Report.objects.get(id=report_id)
            return ReportImage.objects.create(report=report, **validated_data)
        except Report.DoesNotExist:
            raise serializers.ValidationError("Report not found.")


# ============================================================
#   REPORT LIST SERIALIZER (Lightweight for listings)
# ============================================================
class ReportListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing reports with optimized queries."""
    
    reporter_name = serializers.CharField(source="reporter.first_name", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)
    department_name = serializers.CharField(source="department.department.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    image_count = serializers.SerializerMethodField()
    has_images = serializers.SerializerMethodField()
    current_user_liked = serializers.SerializerMethodField()
    
    class Meta:
        model = Report
        fields = [
            "id",
            "title",
            "reporter_name",
            "county_name",
            "department_name",
            "status",
            "status_display",
            "verified_by_ai",
            "ai_confidence",
            "image_required_passed",
            "created_at",
            "image_count",
            "has_images",
            "likes_count",
            "comments_count",
            "views_count",
            "current_user_liked"
        ]
        read_only_fields = fields

    def get_image_count(self, obj):
        return obj.images.count()

    def get_has_images(self, obj):
        return obj.images.exists()
    
    def get_current_user_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


# ============================================================
#   REPORT DETAIL SERIALIZER (Detailed view)
# ============================================================
class ReportDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single report view."""
    
    images = ReportImageSerializer(many=True, read_only=True)
    reporter_name = serializers.CharField(source="reporter.first_name", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)
    subcounty_name = serializers.CharField(source="subcounty.name", read_only=True, allow_null=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True, allow_null=True)
    department_name = serializers.CharField(source="department.department.name", read_only=True, allow_null=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    current_user_liked = serializers.SerializerMethodField()

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
            "subcounty_name",
            "ward", 
            "ward_name",
            "latitude",
            "longitude",
            "department",
            "department_name",
            "status",
            "status_display",
            "verified_by_ai",
            "ai_confidence",
            "image_required_passed",
            "created_at",
            "updated_at",
            "images",
            "likes_count",
            "comments_count",
            "views_count",
            "current_user_liked",
            "government_response",
            "response_date",
            "responded_by",
            "is_development_showcase"
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
            "likes_count",
            "comments_count",
            "views_count",
        ]
    
    def get_current_user_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


# ============================================================
#   REPORT CREATE/UPDATE SERIALIZER (Main serializer)
# ============================================================
class ReportSerializer(serializers.ModelSerializer):
    """
    Serializes report data for creation and update operations.
    
    - Automatically attaches the reporter and role
    - Validates required fields
    - Handles nested image uploads
    """

    # Nested images
    images = ReportImageSerializer(many=True, read_only=True)
    new_images = serializers.ListField(
        child=serializers.ImageField(
            max_length=None, 
            allow_empty_file=False, 
            use_url=False
        ),
        write_only=True,
        required=False,
        help_text="Attach one or more images to this report."
    )
    
    # Read-only display fields
    reporter_name = serializers.CharField(source="reporter.first_name", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)
    department_name = serializers.CharField(source="department.department.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    current_user_liked = serializers.SerializerMethodField()

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
            "status_display",
            "verified_by_ai",
            "ai_confidence",
            "image_required_passed",
            "created_at",
            "updated_at",
            "images",
            "new_images",
            "likes_count",
            "comments_count",
            "views_count",
            "current_user_liked"
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
            "likes_count",
            "comments_count",
            "views_count",
        ]

    def get_current_user_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    # --------------------------------------------------------
    #   VALIDATION LOGIC
    # --------------------------------------------------------
    def validate(self, data):
        """Enhanced validation with comprehensive checks."""
        errors = {}
        
        # Title validation
        title = data.get("title", "").strip()
        if not title:
            errors["title"] = "A report must have a title."
        elif len(title) < 5:
            errors["title"] = "Title must be at least 5 characters long."
        
        # Description validation
        description = data.get("description", "").strip()
        if not description:
            errors["description"] = "Please provide a detailed description."
        elif len(description) < 10:
            errors["description"] = "Description must be at least 10 characters long."
        
        # County validation
        if not data.get("county"):
            errors["county"] = "County is required."
        
        # Location coordinates validation
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        if latitude is not None:
            if not (-90 <= float(latitude) <= 90):
                errors["latitude"] = "Latitude must be between -90 and 90."
        if longitude is not None:
            if not (-180 <= float(longitude) <= 180):
                errors["longitude"] = "Longitude must be between -180 and 180."
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return data

    def validate_title(self, value):
        """Ensure title is unique for the reporter."""
        reporter = self.context.get('request').user
        if Report.objects.filter(title=value.strip(), reporter=reporter).exists():
            raise serializers.ValidationError("You already have a report with this title.")
        return value.strip()

    # --------------------------------------------------------
    #   CREATE METHOD
    # --------------------------------------------------------
    def create(self, validated_data):
        """
        Custom create method:
        - Attaches the reporter and role
        - Handles image uploads
        - Sets image_required_passed flag
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
        - Restricts editing based on status
        - Updates only allowed fields
        - Handles new image uploads
        """
        if not instance.is_editable_by_reporter():
            raise serializers.ValidationError(
                "You cannot edit this report after it has been verified or processed."
            )

        # Extract new images
        new_images = validated_data.pop("new_images", [])
        
        # Update allowed fields
        allowed_fields = ["title", "description", "county", "subcounty", "ward", "latitude", "longitude", "department"]
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)

        # Handle new image uploads
        if new_images:
            for image_file in new_images:
                ReportImage.objects.create(report=instance, image=image_file)
            instance.image_required_passed = True

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
    
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = ["status", "status_display"]

    def validate_status(self, value):
        """Ensure provided status is valid."""
        valid_choices = [choice[0] for choice in ReportStatusChoices.choices]
        if value not in valid_choices:
            raise serializers.ValidationError(f"Invalid status '{value}'. Must be one of: {', '.join(valid_choices)}")
        return value

    def update(self, instance, validated_data):
        new_status = validated_data["status"]
        instance.mark_status(new_status)
        return instance


# ============================================================
#   REPORT STATISTICS SERIALIZER
# ============================================================
class ReportStatsSerializer(serializers.Serializer):
    """Serializer for report statistics and analytics."""
    
    total_reports = serializers.IntegerField()
    verified_reports = serializers.IntegerField()
    pending_reports = serializers.IntegerField()
    rejected_reports = serializers.IntegerField()
    reports_with_images = serializers.IntegerField()
    ai_verified_reports = serializers.IntegerField()
    user_reports_count = serializers.IntegerField()
    user_resolved_reports = serializers.IntegerField()
    reports_by_status = serializers.DictField()
    reports_by_county = serializers.DictField()
    reports_by_department = serializers.DictField()
    recent_reports_count = serializers.IntegerField(help_text="Reports from last 7 days")


# ============================================================
#   REPORT MINIMAL SERIALIZER (For dropdowns/autocomplete)
# ============================================================
class ReportMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for dropdowns and autocomplete fields."""
    
    reporter_name = serializers.CharField(source="reporter.first_name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = ["id", "title", "reporter_name", "status", "status_display", "created_at"]
        read_only_fields = fields


# ============================================================
#   GOVERNMENT DEVELOPMENT SERIALIZERS
# ============================================================
class GovernmentDevelopmentSerializer(serializers.ModelSerializer):
    """Serializer for Government Development projects."""
    county_name = serializers.CharField(source='county.name', read_only=True)
    department_name = serializers.CharField(source='department.department.name', read_only=True)
    created_by_name = serializers.SerializerMethodField()
    is_liked = serializers.SerializerMethodField()
    days_remaining = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    
    class Meta:
        model = GovernmentDevelopment
        fields = [
            'id', 'title', 'description', 'county', 'county_name', 'department', 'department_name',
            'budget', 'start_date', 'expected_completion', 'actual_completion', 'status',
            'progress_percentage', 'progress_updates', 'likes_count', 'comments_count', 'views_count',
            'created_by', 'created_by_name', 'created_at', 'updated_at', 'is_liked',
            'days_remaining', 'is_overdue'
        ]
        read_only_fields = ['created_by', 'created_at', 'updated_at', 'likes_count', 'comments_count', 'views_count']

    def get_created_by_name(self, obj):
        return f"{obj.created_by.first_name} {obj.created_by.last_name}"

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def validate_budget(self, value):
        if value and value < 0:
            raise serializers.ValidationError("Budget cannot be negative.")
        return value

    def validate_start_date(self, value):
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Start date cannot be in the past.")
        return value

    def validate(self, data):
        expected_completion = data.get('expected_completion')
        start_date = data.get('start_date')
        
        if expected_completion and start_date and expected_completion < start_date:
            raise serializers.ValidationError({
                "expected_completion": "Expected completion date cannot be before start date."
            })
        
        return data


class GovernmentDevelopmentProgressSerializer(serializers.ModelSerializer):
    """Serializer for updating project progress."""
    class Meta:
        model = GovernmentDevelopment
        fields = ['progress_percentage', 'progress_updates']

    def validate_progress_percentage(self, value):
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Progress percentage must be between 0 and 100.")
        return value