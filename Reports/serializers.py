# serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError

from .models import Report, ReportImage, GovernmentDevelopment, ReportStatusChoices
from Authentication.models import CustomUser
from Location.models import County, SubCounty, Ward
from Departments.models import CountyDepartment


# =============================================================================
# REPORT IMAGE SERIALIZERS
# =============================================================================

class ReportImageSerializer(serializers.ModelSerializer):
    """Serializer for report images with Cloudinary URL methods."""
    
    image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    image_id = serializers.UUIDField(source='id', read_only=True)

    class Meta:
        model = ReportImage
        fields = [
            "image_id", "image", "image_url", "thumbnail_url", 
            "caption", "uploaded_at"
        ]
        read_only_fields = ["image_id", "uploaded_at"]

    def get_image_url(self, obj):
        """Get full image URL from Cloudinary."""
        return obj.image_url

    def get_thumbnail_url(self, obj):
        """Get thumbnail URL from Cloudinary."""
        return obj.thumbnail_url


class ReportImageUploadSerializer(serializers.ModelSerializer):
    """Serializer for uploading report images."""
    
    class Meta:
        model = ReportImage
        fields = ["image", "caption"]
    
    def create(self, validated_data):
        """Create report image with context-based report assignment."""
        report_id = self.context.get('report_id')
        try:
            report = Report.objects.get(id=report_id)
            return ReportImage.objects.create(report=report, **validated_data)
        except Report.DoesNotExist:
            raise serializers.ValidationError("Report not found.")


# =============================================================================
# REPORT CORE SERIALIZERS
# =============================================================================

class ReportMinimalSerializer(serializers.ModelSerializer):
    """Minimal serializer for report listings and dropdowns."""
    
    reporter_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)

    class Meta:
        model = Report
        fields = [
            "id", "title", "reporter_name", "county_name", 
            "status", "status_display", "created_at"
        ]
        read_only_fields = fields

    def get_reporter_name(self, obj):
        """Get public reporter name with anonymity support."""
        return obj.get_public_reporter_name()


class ReportListSerializer(serializers.ModelSerializer):
    """Serializer for report listing with optimized queries."""
    
    # Basic fields
    reporter_name = serializers.SerializerMethodField()
    county_name = serializers.CharField(source="county.name", read_only=True)
    subcounty_name = serializers.CharField(source="subcounty.name", read_only=True, allow_null=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True, allow_null=True)
    department_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    
    # Image fields
    image_count = serializers.SerializerMethodField()
    has_images = serializers.SerializerMethodField()
    main_image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    
    # Engagement fields
    current_user_liked = serializers.SerializerMethodField()
    engagement_score = serializers.FloatField(read_only=True)
    
    # AI verification
    ai_confidence_percentage = serializers.SerializerMethodField()
    
    # Anonymous reporting
    is_anonymous = serializers.BooleanField(read_only=True)

    class Meta:
        model = Report
        fields = [
            # Core identification
            "id", "title", "description", "status", "status_display",
            "created_at", "updated_at",
            
            # Location information
            "county_name", "subcounty_name", "ward_name",
            
            # Reporter information
            "reporter_name", "role_at_submission", "is_anonymous",
            
            # Department information
            "department_name",
            
            # Image information
            "image_count", "has_images", "main_image_url", "thumbnail_url",
            
            # AI verification
            "verified_by_ai", "ai_confidence", "ai_confidence_percentage",
            "image_required_passed",
            
            # Engagement metrics
            "likes_count", "comments_count", "views_count",
            "current_user_liked", "engagement_score",
        ]
        read_only_fields = fields

    def get_reporter_name(self, obj):
        """Get public reporter name respecting anonymity."""
        return obj.get_public_reporter_name()

    def get_department_name(self, obj):
        """Get department name from related object."""
        if obj.department and obj.department.department:
            return obj.department.department.name
        return None

    def get_image_count(self, obj):
        """Get optimized image count using prefetch cache."""
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache['images'])
        return obj.images.count()

    def get_has_images(self, obj):
        """Check if report has any images."""
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache['images']) > 0
        if getattr(obj, 'image_required_passed', False):
            return True
        return obj.images.exists()
    
    def get_main_image_url(self, obj):
        """Get main image URL for listing display."""
        return obj.get_main_image_url()

    def get_thumbnail_url(self, obj):
        """Get thumbnail URL for listing display."""
        return obj.get_thumbnail_url()
    
    def get_current_user_liked(self, obj):
        """Check if current user liked this report."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_ai_confidence_percentage(self, obj):
        """Convert AI confidence to percentage for display."""
        if obj.ai_confidence:
            return round(obj.ai_confidence * 100, 1)
        return None


class ReportDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for individual report view with full data."""
    
    # Related objects
    images = ReportImageSerializer(many=True, read_only=True)
    
    # Controlled reporter information
    reporter_info = serializers.SerializerMethodField()
    can_view_reporter_details = serializers.SerializerMethodField()
    
    # Display fields
    county_name = serializers.CharField(source="county.name", read_only=True)
    subcounty_name = serializers.CharField(source="subcounty.name", read_only=True, allow_null=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True, allow_null=True)
    department_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    responded_by_name = serializers.CharField(source="responded_by.get_full_name", read_only=True, allow_null=True)
    
    # Image fields
    main_image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()
    
    # Engagement fields
    current_user_liked = serializers.SerializerMethodField()
    engagement_score = serializers.FloatField(read_only=True)
    
    # AI verification
    ai_confidence_percentage = serializers.SerializerMethodField()
    
    # Development showcase
    development_progress_display = serializers.SerializerMethodField()

    class Meta:
        model = Report
        fields = [
            # Core identification
            "id", "title", "description", 
            
            # Reporter information
            "reporter_info", "can_view_reporter_details", "is_anonymous",
            
            # Location information
            "county", "county_name", "subcounty", "subcounty_name", 
            "ward", "ward_name", "latitude", "longitude",
            
            # Department assignment
            "department", "department_name",
            
            # Status tracking
            "status", "status_display", "created_at", "updated_at",
            
            # AI verification
            "verified_by_ai", "ai_confidence", "ai_confidence_percentage",
            "image_required_passed",
            
            # Media
            "images", "main_image_url", "thumbnail_url", "image_count",
            
            # Social engagement
            "likes_count", "comments_count", "views_count",
            "current_user_liked", "engagement_score",
            
            # Government response
            "government_response", "response_date", "responded_by", "responded_by_name",
            
            # Development showcase
            "is_development_showcase", "development_budget", 
            "completion_date", "development_progress", "development_progress_display"
        ]
        read_only_fields = [
            "id", "reporter", "role_at_submission", "created_at", "updated_at",
            "verified_by_ai", "ai_confidence", "image_required_passed",
            "likes_count", "comments_count", "views_count", "response_date",
            "responded_by", "engagement_score"
        ]
    
    def get_reporter_info(self, obj):
        """Get reporter information with access control."""
        request = self.context.get('request')
        if request and request.user.is_authenticated and obj.can_view_reporter_details(request.user):
            return {
                'name': obj.reporter.get_full_name(),
                'email': obj.reporter.email,
                'role': obj.role_at_submission,
                'is_anonymous': obj.is_anonymous,
                'full_access': True
            }
        else:
            return obj.get_public_reporter_info()
    
    def get_can_view_reporter_details(self, obj):
        """Check if current user can view reporter details."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_view_reporter_details(request.user)
        return False
    
    def get_department_name(self, obj):
        """Get department name from related object."""
        if obj.department and obj.department.department:
            return obj.department.department.name
        return None
    
    def get_main_image_url(self, obj):
        """Get main image URL."""
        return obj.get_main_image_url()

    def get_thumbnail_url(self, obj):
        """Get thumbnail URL."""
        return obj.get_thumbnail_url()

    def get_image_count(self, obj):
        """Get total image count."""
        return obj.images.count()
    
    def get_current_user_liked(self, obj):
        """Check if current user liked this report."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_ai_confidence_percentage(self, obj):
        """Convert AI confidence to percentage."""
        if obj.ai_confidence:
            return round(obj.ai_confidence * 100, 1)
        return None

    def get_development_progress_display(self, obj):
        """Format development progress for display."""
        if obj.is_development_showcase and obj.development_progress is not None:
            return f"{obj.development_progress}%"
        return None


class ReportCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating reports with image upload support."""
    
    new_images = serializers.ListField(
        child=serializers.ImageField(
            max_length=10000000,
            allow_empty_file=False,
            use_url=False
        ),
        write_only=True,
        required=False,
        help_text="List of images to upload with the report"
    )
    
    # Anonymous reporting
    is_anonymous = serializers.BooleanField(
        default=False,
        help_text="Whether to hide reporter identity"
    )
    anonymous_display_name = serializers.CharField(
        max_length=100, 
        required=False, 
        allow_blank=True,
        default="Anonymous Citizen",
        help_text="Display name for anonymous reports"
    )

    class Meta:
        model = Report
        fields = [
            # Core fields
            "title", "description",
            
            # Location
            "county", "subcounty", "ward", "latitude", "longitude",
            
            # Department
            "department",
            
            # Priority
            "priority",
            
            # Anonymous reporting
            "is_anonymous", "anonymous_display_name",
            
            # Images
            "new_images",
        ]

    def validate(self, data):
        """Comprehensive validation for report data."""
        errors = {}
        
        # Title validation
        title = data.get("title", "").strip()
        if not title:
            errors["title"] = "A report title is required."
        elif len(title) < 5:
            errors["title"] = "Title must be at least 5 characters long."
        elif len(title) > 255:
            errors["title"] = "Title cannot exceed 255 characters."
        
        # Description validation
        description = data.get("description", "").strip()
        if not description:
            errors["description"] = "Please provide a detailed description of the issue."
        elif len(description) < 10:
            errors["description"] = "Description must be at least 10 characters long."
        elif len(description) > 5000:
            errors["description"] = "Description cannot exceed 5000 characters."
        
        # County validation
        if not data.get("county"):
            errors["county"] = "Please select a county."
        
        # Location coordinates validation
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        if latitude is not None:
            try:
                lat_float = float(latitude)
                if not (-90 <= lat_float <= 90):
                    errors["latitude"] = "Latitude must be between -90 and 90 degrees."
            except (TypeError, ValueError):
                errors["latitude"] = "Latitude must be a valid number."
        
        if longitude is not None:
            try:
                lon_float = float(longitude)
                if not (-180 <= lon_float <= 180):
                    errors["longitude"] = "Longitude must be between -180 and 180 degrees."
            except (TypeError, ValueError):
                errors["longitude"] = "Longitude must be a valid number."
        
        # Anonymous display name validation
        if data.get('is_anonymous', False):
            display_name = data.get('anonymous_display_name', '').strip()
            if not display_name:
                data['anonymous_display_name'] = "Anonymous Citizen"
            elif len(display_name) > 100:
                errors['anonymous_display_name'] = "Display name cannot exceed 100 characters."
        
        # Image validation
        new_images = data.get("new_images", [])
        if new_images and len(new_images) > 10:
            errors["new_images"] = "You can upload a maximum of 10 images per report."
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return data

    def validate_title(self, value):
        """Validate title uniqueness for the user."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            recent_cutoff = timezone.now() - timezone.timedelta(hours=24)
            duplicate_exists = Report.objects.filter(
                title=value.strip(),
                reporter=request.user,
                created_at__gte=recent_cutoff
            ).exists()
            
            if duplicate_exists and self.instance is None:
                raise serializers.ValidationError(
                    "You have already submitted a report with this title recently. "
                    "Please use a different title or wait 24 hours."
                )
        return value.strip()

    @transaction.atomic
    def create(self, validated_data):
        """Create report with image uploads in a transaction."""
        new_images = validated_data.pop('new_images', [])
        
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated to create a report.")
        
        reporter = request.user
        
        # Handle anonymous display name
        if validated_data.get('is_anonymous', False):
            display_name = validated_data.get('anonymous_display_name', '').strip()
            if not display_name:
                validated_data['anonymous_display_name'] = "Anonymous Citizen"
        
        # Create the report
        try:
            report = Report.objects.create(
                reporter=reporter,
                role_at_submission=reporter.role,
                **validated_data
            )
        except Exception as e:
            raise serializers.ValidationError(f"Failed to create report: {str(e)}")
        
        # Handle image uploads
        if new_images:
            try:
                for image_file in new_images:
                    ReportImage.objects.create(
                        report=report, 
                        image=image_file,
                        caption=f"Image evidence for {report.title}"
                    )
                
                report.image_required_passed = True
                report.save(update_fields=["image_required_passed"])
                
            except Exception as e:
                raise serializers.ValidationError(f"Failed to upload images: {str(e)}")

        return report

    @transaction.atomic
    def update(self, instance, validated_data):
        """Update report with new images."""
        if not instance.is_editable_by_reporter():
            raise serializers.ValidationError({
                "detail": "This report can no longer be edited. "
                         "Only reports with 'Submitted' status can be modified."
            })

        new_images = validated_data.pop('new_images', [])
        
        # Update allowed fields
        allowed_fields = [
            "title", "description", "county", "subcounty", "ward", 
            "latitude", "longitude", "department", "priority",
            "is_anonymous", "anonymous_display_name"
        ]
        
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)

        # Handle new image uploads
        if new_images:
            current_count = instance.images.count()
            if current_count + len(new_images) > 10:
                raise serializers.ValidationError({
                    "new_images": f"Cannot add {len(new_images)} images. "
                                f"Report already has {current_count} images (max 10)."
                })
            
            for image_file in new_images:
                ReportImage.objects.create(
                    report=instance, 
                    image=image_file,
                    caption=f"Additional image for {instance.title}"
                )
            
            instance.image_required_passed = True

        instance.updated_at = timezone.now()
        instance.save()
        
        return instance


class ReportSerializer(ReportCreateSerializer):
    """Main report serializer that combines create/update with read capabilities."""
    
    # Add read-only fields for general use
    reporter_name = serializers.SerializerMethodField(read_only=True)
    county_name = serializers.CharField(source="county.name", read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    images = ReportImageSerializer(many=True, read_only=True)

    class Meta(ReportCreateSerializer.Meta):
        fields = ReportCreateSerializer.Meta.fields + [
            "id", "status", "status_display", "reporter_name", "county_name",
            "verified_by_ai", "ai_confidence", "image_required_passed",
            "created_at", "updated_at", "images"
        ]
        read_only_fields = [
            "id", "status", "verified_by_ai", "ai_confidence", 
            "image_required_passed", "created_at", "updated_at"
        ]

    def get_reporter_name(self, obj):
        """Get public reporter name."""
        return obj.get_public_reporter_name()


class ReportStatusUpdateSerializer(serializers.ModelSerializer):
    """Serializer for updating report status."""
    
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    previous_status = serializers.CharField(read_only=True)

    class Meta:
        model = Report
        fields = ["status", "status_display", "previous_status"]
        read_only_fields = ["status_display", "previous_status"]

    def validate_status(self, value):
        """Validate status choice."""
        valid_choices = [choice[0] for choice in ReportStatusChoices.choices]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Invalid status '{value}'. Must be one of: {', '.join(valid_choices)}"
            )
        return value

    def update(self, instance, validated_data):
        """Update report status with tracking."""
        new_status = validated_data["status"]
        self.previous_status = instance.status
        instance.mark_status(new_status)
        return instance

    def to_representation(self, instance):
        """Include previous status in response."""
        representation = super().to_representation(instance)
        representation['previous_status'] = getattr(self, 'previous_status', instance.status)
        return representation


# =============================================================================
# REPORT STATISTICS SERIALIZER
# =============================================================================

class ReportStatsSerializer(serializers.Serializer):
    """Serializer for report statistics and analytics."""
    
    # Basic counts
    total_reports = serializers.IntegerField()
    verified_reports = serializers.IntegerField()
    pending_reports = serializers.IntegerField()
    rejected_reports = serializers.IntegerField()
    reports_with_images = serializers.IntegerField()
    ai_verified_reports = serializers.IntegerField()
    
    # User-specific stats
    user_reports_count = serializers.IntegerField()
    user_resolved_reports = serializers.IntegerField()
    
    # Time-based stats
    recent_reports_count = serializers.IntegerField(help_text="Reports from last 7 days")
    today_reports_count = serializers.IntegerField(help_text="Reports submitted today")
    
    # Distribution stats
    reports_by_status = serializers.DictField()
    reports_by_county = serializers.DictField()
    reports_by_department = serializers.DictField()
    
    # Engagement stats
    total_likes = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    total_views = serializers.IntegerField()
    average_engagement_score = serializers.FloatField()


# =============================================================================
# GOVERNMENT DEVELOPMENT SERIALIZERS
# =============================================================================

class GovernmentDevelopmentSerializer(serializers.ModelSerializer):
    """Serializer for government development projects."""
    
    # Related object display fields
    county_name = serializers.CharField(source='county.name', read_only=True)
    department_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    
    # Engagement fields
    is_liked = serializers.SerializerMethodField()
    
    # Progress fields
    days_remaining = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    progress_status = serializers.SerializerMethodField()
    
    # Budget formatting
    budget_formatted = serializers.SerializerMethodField()

    class Meta:
        model = GovernmentDevelopment
        fields = [
            # Core information
            'id', 'title', 'description',
            
            # Location and department
            'county', 'county_name', 'department', 'department_name',
            
            # Project details
            'budget', 'budget_formatted', 'start_date', 'expected_completion', 
            'actual_completion', 'status',
            
            # Progress tracking
            'progress_percentage', 'progress_status', 'progress_updates',
            
            # Engagement metrics
            'likes_count', 'comments_count', 'views_count', 'is_liked',
            
            # Metadata
            'created_by', 'created_by_name', 'created_by_email',
            'created_at', 'updated_at',
            
            # Calculated fields
            'days_remaining', 'is_overdue'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at', 
            'likes_count', 'comments_count', 'views_count',
            'days_remaining', 'is_overdue'
        ]

    def get_department_name(self, obj):
        """Get department name from related object."""
        if obj.department and obj.department.department:
            return obj.department.department.name
        return None

    def get_created_by_name(self, obj):
        """Get creator's full name."""
        if obj.created_by:
            return obj.created_by.get_full_name()
        return None

    def get_is_liked(self, obj):
        """Check if current user liked this project."""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_progress_status(self, obj):
        """Get human-readable progress status."""
        if obj.progress_percentage == 0:
            return "Not Started"
        elif obj.progress_percentage < 25:
            return "Early Stage"
        elif obj.progress_percentage < 50:
            return "In Progress"
        elif obj.progress_percentage < 75:
            return "Halfway"
        elif obj.progress_percentage < 100:
            return "Nearly Complete"
        else:
            return "Completed"

    def get_budget_formatted(self, obj):
        """Format budget as currency."""
        if obj.budget:
            return f"KSh {obj.budget:,.2f}"
        return None

    def validate_budget(self, value):
        """Validate budget is non-negative."""
        if value and value < 0:
            raise serializers.ValidationError("Budget cannot be negative.")
        return value

    def validate_start_date(self, value):
        """Validate start date is not in the past."""
        if value and value < timezone.now().date():
            raise serializers.ValidationError("Start date cannot be in the past.")
        return value

    def validate(self, data):
        """Validate date relationships."""
        expected_completion = data.get('expected_completion')
        start_date = data.get('start_date')
        actual_completion = data.get('actual_completion')
        
        if expected_completion and start_date and expected_completion < start_date:
            raise serializers.ValidationError({
                "expected_completion": "Expected completion date cannot be before start date."
            })
        
        if actual_completion and start_date and actual_completion < start_date:
            raise serializers.ValidationError({
                "actual_completion": "Actual completion date cannot be before start date."
            })
        
        return data


class GovernmentDevelopmentProgressSerializer(serializers.ModelSerializer):
    """Serializer for updating government development progress."""
    
    previous_progress = serializers.IntegerField(read_only=True)
    progress_change = serializers.IntegerField(read_only=True)

    class Meta:
        model = GovernmentDevelopment
        fields = [
            'progress_percentage', 'progress_updates',
            'previous_progress', 'progress_change'
        ]
        read_only_fields = ['previous_progress', 'progress_change']

    def validate_progress_percentage(self, value):
        """Validate progress percentage range."""
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Progress percentage must be between 0 and 100.")
        return value

    def update(self, instance, validated_data):
        """Update progress with change tracking."""
        previous_progress = instance.progress_percentage
        progress_percentage = validated_data.get('progress_percentage', previous_progress)
        progress_updates = validated_data.get('progress_updates')
        
        instance.update_progress(progress_percentage, progress_updates)
        
        self.previous_progress = previous_progress
        self.progress_change = progress_percentage - previous_progress
        
        return instance

    def to_representation(self, instance):
        """Include progress change information."""
        representation = super().to_representation(instance)
        representation['previous_progress'] = getattr(self, 'previous_progress', instance.progress_percentage)
        representation['progress_change'] = getattr(self, 'progress_change', 0)
        return representation
