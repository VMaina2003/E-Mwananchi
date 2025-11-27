# serializers.py - PRODUCTION READY VERSION
from rest_framework import serializers
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
import os

from .models import Report, ReportImage, GovernmentDevelopment, ReportStatusChoices
from Authentication.models import CustomUser
from Location.models import County, SubCounty, Ward
from Departments.models import CountyDepartment


class ReportImageSerializer(serializers.ModelSerializer):
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
        return obj.image_url

    def get_thumbnail_url(self, obj):
        return obj.thumbnail_url


class ReportImageUploadSerializer(serializers.ModelSerializer):
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


class ReportBaseSerializer(serializers.ModelSerializer):
    reporter_name = serializers.SerializerMethodField()
    county_name = serializers.CharField(source="county.name", read_only=True)
    subcounty_name = serializers.CharField(source="subcounty.name", read_only=True, allow_null=True)
    ward_name = serializers.CharField(source="ward.name", read_only=True, allow_null=True)
    department_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = Report
        fields = []

    def get_reporter_name(self, obj):
        return obj.get_public_reporter_name()

    def get_department_name(self, obj):
        if obj.department and obj.department.department:
            return obj.department.department.name
        return None


class ReportMinimalSerializer(ReportBaseSerializer):
    class Meta:
        model = Report
        fields = [
            "id", "title", "reporter_name", "county_name", 
            "status", "status_display", "created_at"
        ]
        read_only_fields = fields


class ReportListSerializer(ReportBaseSerializer):
    image_count = serializers.SerializerMethodField()
    has_images = serializers.SerializerMethodField()
    main_image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    current_user_liked = serializers.SerializerMethodField()
    engagement_score = serializers.FloatField(read_only=True)
    ai_confidence_percentage = serializers.SerializerMethodField()
    is_development_showcase = serializers.BooleanField(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id", "title", "description", "status", "status_display",
            "created_at", "updated_at", "county_name", "subcounty_name", "ward_name",
            "reporter_name", "role_at_submission", "is_anonymous", "department_name",
            "image_count", "has_images", "main_image_url", "thumbnail_url",
            "verified_by_ai", "ai_confidence", "ai_confidence_percentage",
            "image_required_passed", "likes_count", "comments_count", "views_count",
            "current_user_liked", "engagement_score", "is_development_showcase",
            "development_budget", "development_progress"
        ]
        read_only_fields = fields

    def get_image_count(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache['images'])
        return obj.images.count()

    def get_has_images(self, obj):
        if hasattr(obj, '_prefetched_objects_cache') and 'images' in obj._prefetched_objects_cache:
            return len(obj._prefetched_objects_cache['images']) > 0
        if getattr(obj, 'image_required_passed', False):
            return True
        return obj.images.exists()
    
    def get_main_image_url(self, obj):
        return obj.get_main_image_url()

    def get_thumbnail_url(self, obj):
        return obj.get_thumbnail_url()
    
    def get_current_user_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_ai_confidence_percentage(self, obj):
        if obj.ai_confidence:
            return round(obj.ai_confidence * 100, 1)
        return None


class ReportDetailSerializer(ReportBaseSerializer):
    images = ReportImageSerializer(many=True, read_only=True)
    reporter_info = serializers.SerializerMethodField()
    can_view_reporter_details = serializers.SerializerMethodField()
    responded_by_name = serializers.CharField(source="responded_by.get_full_name", read_only=True, allow_null=True)
    main_image_url = serializers.SerializerMethodField()
    thumbnail_url = serializers.SerializerMethodField()
    image_count = serializers.SerializerMethodField()
    current_user_liked = serializers.SerializerMethodField()
    engagement_score = serializers.FloatField(read_only=True)
    ai_confidence_percentage = serializers.SerializerMethodField()
    development_progress_display = serializers.SerializerMethodField()
    is_development_showcase = serializers.BooleanField(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id", "title", "description", "reporter_info", "can_view_reporter_details", 
            "is_anonymous", "county", "county_name", "subcounty", "subcounty_name", 
            "ward", "ward_name", "latitude", "longitude", "department", "department_name",
            "status", "status_display", "created_at", "updated_at", "verified_by_ai", 
            "ai_confidence", "ai_confidence_percentage", "image_required_passed",
            "images", "main_image_url", "thumbnail_url", "image_count", "likes_count", 
            "comments_count", "views_count", "current_user_liked", "engagement_score",
            "government_response", "response_date", "responded_by", "responded_by_name",
            "is_development_showcase", "development_budget", "completion_date", 
            "development_progress", "development_progress_display"
        ]
        read_only_fields = [
            "id", "reporter", "role_at_submission", "created_at", "updated_at",
            "verified_by_ai", "ai_confidence", "image_required_passed",
            "likes_count", "comments_count", "views_count", "response_date",
            "responded_by", "engagement_score"
        ]
    
    def get_reporter_info(self, obj):
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
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.can_view_reporter_details(request.user)
        return False
    
    def get_main_image_url(self, obj):
        return obj.get_main_image_url()

    def get_thumbnail_url(self, obj):
        return obj.get_thumbnail_url()

    def get_image_count(self, obj):
        return obj.images.count()
    
    def get_current_user_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_ai_confidence_percentage(self, obj):
        if obj.ai_confidence:
            return round(obj.ai_confidence * 100, 1)
        return None

    def get_development_progress_display(self, obj):
        if obj.is_development_showcase and obj.development_progress is not None:
            return f"{obj.development_progress}%"
        return None


class ReportCreateSerializer(serializers.ModelSerializer):
    images = serializers.FileField(
        required=False,
        write_only=True,
        help_text="Image files to upload with this report"
    )
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
    is_development_showcase = serializers.BooleanField(
        default=False,
        required=False,
        help_text="Mark as true for government development projects"
    )
    development_budget = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
        help_text="Budget allocated for development project"
    )
    completion_date = serializers.DateField(
        required=False,
        allow_null=True,
        help_text="Expected completion date for development project"
    )
    development_progress = serializers.IntegerField(
        default=0,
        required=False,
        help_text="Progress percentage for development project"
    )

    class Meta:
        model = Report
        fields = [
            "title", "description", "county", "subcounty", "ward", 
            "latitude", "longitude", "department", "priority",
            "is_anonymous", "anonymous_display_name", "images",
            "is_development_showcase", "development_budget", 
            "completion_date", "development_progress"
        ]

    def validate(self, data):
        errors = {}
        
        title = data.get("title", "").strip()
        if not title:
            errors["title"] = "A report title is required."
        elif len(title) < 5:
            errors["title"] = "Title must be at least 5 characters long."
        elif len(title) > 255:
            errors["title"] = "Title cannot exceed 255 characters."
        
        description = data.get("description", "").strip()
        if not description:
            errors["description"] = "Please provide a detailed description of the issue."
        elif len(description) < 10:
            errors["description"] = "Description must be at least 10 characters long."
        elif len(description) > 5000:
            errors["description"] = "Description cannot exceed 5000 characters."
        
        if not data.get("county"):
            errors["county"] = "Please select a county."
        
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        if latitude is not None and latitude != "":
            try:
                lat_float = float(latitude)
                if not (-90 <= lat_float <= 90):
                    errors["latitude"] = "Latitude must be between -90 and 90 degrees."
            except (TypeError, ValueError):
                errors["latitude"] = "Latitude must be a valid number."
        
        if longitude is not None and longitude != "":
            try:
                lon_float = float(longitude)
                if not (-180 <= lon_float <= 180):
                    errors["longitude"] = "Longitude must be between -180 and 180 degrees."
            except (TypeError, ValueError):
                errors["longitude"] = "Longitude must be a valid number."
        
        if data.get('is_anonymous', False):
            display_name = data.get('anonymous_display_name', '').strip()
            if not display_name:
                data['anonymous_display_name'] = "Anonymous Citizen"
            elif len(display_name) > 100:
                errors['anonymous_display_name'] = "Display name cannot exceed 100 characters."
        
        if data.get('is_development_showcase', False):
            development_progress = data.get('development_progress', 0)
            if not (0 <= development_progress <= 100):
                errors['development_progress'] = "Development progress must be between 0 and 100."
            
            development_budget = data.get('development_budget')
            if development_budget and development_budget < 0:
                errors['development_budget'] = "Development budget cannot be negative."
        
        request = self.context.get('request')
        if request and hasattr(request, 'FILES'):
            images = request.FILES.getlist('images')
            if images:
                if len(images) > 10:
                    errors["images"] = ["You can upload a maximum of 10 images per report."]
                
                for i, image in enumerate(images):
                    if hasattr(image, 'size') and image.size > 10 * 1024 * 1024:
                        errors.setdefault("images", []).append(
                            f"Image {i+1} is too large ({(image.size / 1024 / 1024):.1f}MB). Maximum size is 10MB."
                        )
                    
                    if hasattr(image, 'content_type'):
                        allowed_types = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp']
                        if image.content_type not in allowed_types:
                            errors.setdefault("images", []).append(
                                f"Image {i+1} must be JPEG, PNG, or WebP format. Found: {image.content_type}"
                            )
                    else:
                        if hasattr(image, 'name'):
                            allowed_extensions = ['.jpg', '.jpeg', '.png', '.webp']
                            file_extension = os.path.splitext(image.name)[1].lower()
                            if file_extension not in allowed_extensions:
                                errors.setdefault("images", []).append(
                                    f"Image {i+1} must be JPEG, PNG, or WebP format. Found: {file_extension}"
                                )
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return data

    def validate_title(self, value):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            recent_cutoff = timezone.now() - timezone.timedelta(hours=1)
            duplicate_exists = Report.objects.filter(
                title=value.strip(),
                reporter=request.user,
                created_at__gte=recent_cutoff
            ).exists()
            
            if duplicate_exists and self.instance is None:
                raise serializers.ValidationError(
                    "You have already submitted a report with this title recently. "
                    "Please use a different title or wait a while."
                )
        return value.strip()

    @transaction.atomic
    def create(self, validated_data):
        validated_data.pop('images', None)
        
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            raise serializers.ValidationError("User must be authenticated to create a report.")
        
        reporter = request.user
        
        if validated_data.get('is_anonymous', False):
            display_name = validated_data.get('anonymous_display_name', '').strip()
            if not display_name:
                validated_data['anonymous_display_name'] = "Anonymous Citizen"
        
        try:
            report = Report.objects.create(
                reporter=reporter,
                role_at_submission=reporter.role,
                **validated_data
            )
            
            if request and hasattr(request, 'FILES'):
                images = request.FILES.getlist('images')
                if images:
                    for image_file in images:
                        ReportImage.objects.create(
                            report=report, 
                            image=image_file,
                            caption=f"Image evidence for {report.title}"
                        )
                    
                    report.image_required_passed = True
                    report.save(update_fields=["image_required_passed"])
            
            return report
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Report creation failed: {str(e)}")
            raise serializers.ValidationError(f"Failed to create report: {str(e)}")


class ReportUpdateSerializer(serializers.ModelSerializer):
    images = serializers.FileField(
        required=False,
        write_only=True,
        help_text="Additional images to upload"
    )
    is_development_showcase = serializers.BooleanField(required=False)
    development_budget = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True
    )
    completion_date = serializers.DateField(required=False, allow_null=True)
    development_progress = serializers.IntegerField(required=False)

    class Meta:
        model = Report
        fields = [
            "title", "description", "county", "subcounty", "ward", 
            "latitude", "longitude", "department", "priority",
            "is_anonymous", "anonymous_display_name", "images",
            "is_development_showcase", "development_budget", 
            "completion_date", "development_progress"
        ]

    def validate(self, data):
        data.pop('images', None)
        
        errors = {}
        
        title = data.get("title")
        if title:
            title = title.strip()
            if len(title) < 5:
                errors["title"] = "Title must be at least 5 characters long."
            elif len(title) > 255:
                errors["title"] = "Title cannot exceed 255 characters."
        
        description = data.get("description")
        if description:
            description = description.strip()
            if len(description) < 10:
                errors["description"] = "Description must be at least 10 characters long."
            elif len(description) > 5000:
                errors["description"] = "Description cannot exceed 5000 characters."
        
        if data.get('is_development_showcase', False):
            development_progress = data.get('development_progress', 0)
            if not (0 <= development_progress <= 100):
                errors['development_progress'] = "Development progress must be between 0 and 100."
        
        request = self.context.get('request')
        if request and hasattr(request, 'FILES'):
            images_data = request.FILES.getlist('images')
            if images_data and len(images_data) > 10:
                errors["images"] = ["You can upload a maximum of 10 images per report."]
        
        if errors:
            raise serializers.ValidationError(errors)
        
        return data

    @transaction.atomic
    def update(self, instance, validated_data):
        if not instance.is_editable_by_reporter():
            raise serializers.ValidationError({
                "detail": "This report can no longer be edited. Only reports with 'Submitted' status can be modified."
            })

        validated_data.pop('images', None)
        
        allowed_fields = [
            "title", "description", "county", "subcounty", "ward", 
            "latitude", "longitude", "department", "priority",
            "is_anonymous", "anonymous_display_name", "is_development_showcase",
            "development_budget", "completion_date", "development_progress"
        ]
        
        for field, value in validated_data.items():
            if field in allowed_fields:
                setattr(instance, field, value)

        request = self.context.get('request')
        if request and hasattr(request, 'FILES'):
            images_data = request.FILES.getlist('images')
            if images_data:
                current_count = instance.images.count()
                if current_count + len(images_data) > 10:
                    raise serializers.ValidationError({
                        "images": [f"Cannot add {len(images_data)} images. Report already has {current_count} images (max 10)."]
                    })
                
                for image_file in images_data:
                    ReportImage.objects.create(
                        report=instance, 
                        image=image_file,
                        caption=f"Additional image for {instance.title}"
                    )
                
                instance.image_required_passed = True

        instance.updated_at = timezone.now()
        instance.save()
        
        return instance


class ReportSerializer(ReportBaseSerializer):
    images = ReportImageSerializer(many=True, read_only=True)
    current_user_liked = serializers.SerializerMethodField()
    is_development_showcase = serializers.BooleanField(read_only=True)

    class Meta:
        model = Report
        fields = [
            "id", "title", "description", "status", "status_display",
            "county", "county_name", "subcounty", "subcounty_name", 
            "ward", "ward_name", "department", "department_name",
            "latitude", "longitude", "priority", "is_anonymous",
            "verified_by_ai", "ai_confidence", "image_required_passed",
            "likes_count", "comments_count", "views_count", "current_user_liked",
            "government_response", "response_date", "responded_by",
            "created_at", "updated_at", "images", "reporter_name",
            "is_development_showcase", "development_budget", 
            "completion_date", "development_progress"
        ]
        read_only_fields = [
            "id", "status", "verified_by_ai", "ai_confidence", 
            "image_required_passed", "likes_count", "comments_count", 
            "views_count", "response_date", "responded_by", "created_at", 
            "updated_at", "reporter_name"
        ]

    def get_current_user_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False


class ReportStatusUpdateSerializer(serializers.ModelSerializer):
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    previous_status = serializers.CharField(read_only=True)

    class Meta:
        model = Report
        fields = ["status", "status_display", "previous_status"]
        read_only_fields = ["status_display", "previous_status"]

    def validate_status(self, value):
        valid_choices = [choice[0] for choice in ReportStatusChoices.choices]
        if value not in valid_choices:
            raise serializers.ValidationError(
                f"Invalid status '{value}'. Must be one of: {', '.join(valid_choices)}"
            )
        return value

    def update(self, instance, validated_data):
        new_status = validated_data["status"]
        self.previous_status = instance.status
        instance.mark_status(new_status)
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['previous_status'] = getattr(self, 'previous_status', instance.status)
        return representation


class ReportStatsSerializer(serializers.Serializer):
    total_reports = serializers.IntegerField()
    verified_reports = serializers.IntegerField()
    pending_reports = serializers.IntegerField()
    resolved_reports = serializers.IntegerField()
    rejected_reports = serializers.IntegerField()
    reports_with_images = serializers.IntegerField()
    ai_verified_reports = serializers.IntegerField()
    user_reports_count = serializers.IntegerField()
    user_resolved_reports = serializers.IntegerField()
    recent_reports_count = serializers.IntegerField()
    today_reports_count = serializers.IntegerField()
    reports_by_status = serializers.DictField()
    reports_by_county = serializers.DictField()
    reports_by_department = serializers.DictField()
    total_likes = serializers.IntegerField()
    total_comments = serializers.IntegerField()
    total_views = serializers.IntegerField()
    average_engagement_score = serializers.FloatField()


class GovernmentDevelopmentSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source='county.name', read_only=True)
    department_name = serializers.SerializerMethodField()
    created_by_name = serializers.SerializerMethodField()
    created_by_email = serializers.CharField(source='created_by.email', read_only=True)
    is_liked = serializers.SerializerMethodField()
    days_remaining = serializers.ReadOnlyField()
    is_overdue = serializers.ReadOnlyField()
    progress_status = serializers.SerializerMethodField()
    budget_formatted = serializers.SerializerMethodField()

    class Meta:
        model = GovernmentDevelopment
        fields = [
            'id', 'title', 'description', 'county', 'county_name', 
            'department', 'department_name', 'budget', 'budget_formatted', 
            'start_date', 'expected_completion', 'actual_completion', 'status',
            'progress_percentage', 'progress_status', 'progress_updates',
            'likes_count', 'comments_count', 'views_count', 'is_liked',
            'created_by', 'created_by_name', 'created_by_email',
            'created_at', 'updated_at', 'days_remaining', 'is_overdue'
        ]
        read_only_fields = [
            'created_by', 'created_at', 'updated_at', 
            'likes_count', 'comments_count', 'views_count',
            'days_remaining', 'is_overdue'
        ]

    def get_department_name(self, obj):
        if obj.department and obj.department.department:
            return obj.department.department.name
        return None

    def get_created_by_name(self, obj):
        if obj.created_by:
            return obj.created_by.get_full_name()
        return None

    def get_is_liked(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.likes.filter(id=request.user.id).exists()
        return False

    def get_progress_status(self, obj):
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
        if obj.budget:
            return f"KSh {obj.budget:,.2f}"
        return None

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
        if not (0 <= value <= 100):
            raise serializers.ValidationError("Progress percentage must be between 0 and 100.")
        return value

    def update(self, instance, validated_data):
        previous_progress = instance.progress_percentage
        progress_percentage = validated_data.get('progress_percentage', previous_progress)
        progress_updates = validated_data.get('progress_updates')
        
        instance.update_progress(progress_percentage, progress_updates)
        
        self.previous_progress = previous_progress
        self.progress_change = progress_percentage - previous_progress
        
        return instance

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['previous_progress'] = getattr(self, 'previous_progress', instance.progress_percentage)
        representation['progress_change'] = getattr(self, 'progress_change', 0)
        return representation