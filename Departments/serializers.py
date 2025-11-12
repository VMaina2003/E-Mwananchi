from rest_framework import serializers
from django.contrib.auth import get_user_model
from Location.models import County
from .models import Department, CountyDepartment, DepartmentOfficial

User = get_user_model()


# ============================================================
#   DEPARTMENT SERIALIZER
# ============================================================
class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "description", "created_at", "updated_at"]
        read_only_fields = ["id", "created_at", "updated_at"]


# ============================================================
#   COUNTY DEPARTMENT SERIALIZER
# ============================================================
class CountyDepartmentSerializer(serializers.ModelSerializer):
    # Display fields for frontend
    county_name = serializers.CharField(source='county.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)
    
    # Writeable fields for creation/updates
    county = serializers.PrimaryKeyRelatedField(queryset=County.objects.all())
    department = serializers.PrimaryKeyRelatedField(queryset=Department.objects.all())

    class Meta:
        model = CountyDepartment
        fields = [
            "id",
            "county",
            "county_name",
            "department", 
            "department_name",
            "email",
            "phone_number",
            "office_location",
            "is_active",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        # Prevent duplicates of same department in the same county
        county = attrs.get("county")
        department = attrs.get("department")
        
        # Exclude current instance if updating
        instance = getattr(self, 'instance', None)
        if instance:
            existing = CountyDepartment.objects.filter(
                county=county, 
                department=department
            ).exclude(id=instance.id)
        else:
            existing = CountyDepartment.objects.filter(county=county, department=department)
            
        if existing.exists():
            raise serializers.ValidationError(
                f"{department.name} department already exists in {county.name}."
            )
        return attrs

    def to_representation(self, instance):
        """Custom representation to include nested data"""
        representation = super().to_representation(instance)
        # Include full county and department objects for frontend
        representation['county_data'] = {
            'id': instance.county.id,
            'name': instance.county.name,
            'code': instance.county.code
        }
        representation['department_data'] = {
            'id': instance.department.id,
            'name': instance.department.name,
            'description': instance.department.description
        }
        return representation


# ============================================================
#   COUNTY DEPARTMENT MINIMAL SERIALIZER (For dropdowns)
# ============================================================
class CountyDepartmentMinimalSerializer(serializers.ModelSerializer):
    county_name = serializers.CharField(source='county.name', read_only=True)
    department_name = serializers.CharField(source='department.name', read_only=True)

    class Meta:
        model = CountyDepartment
        fields = [
            "id",
            "county_name",
            "department_name",
            "is_active"
        ]


# ============================================================
#   DEPARTMENT OFFICIAL SERIALIZER
# ============================================================
class DepartmentOfficialSerializer(serializers.ModelSerializer):
    # Display fields for frontend
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    user_email = serializers.CharField(source='user.email', read_only=True)
    user_role = serializers.CharField(source='user.role', read_only=True)
    county_department_name = serializers.CharField(source='county_department.__str__', read_only=True)
    county_name = serializers.CharField(source='county_department.county.name', read_only=True)
    department_name = serializers.CharField(source='county_department.department.name', read_only=True)
    
    # Writeable fields for creation/updates
    user = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.filter(role__in=["county_official", "admin", "superadmin"]),
        help_text="Assign an existing user by ID (must have county_official, admin, or superadmin role)"
    )
    county_department = serializers.PrimaryKeyRelatedField(queryset=CountyDepartment.objects.all())

    class Meta:
        model = DepartmentOfficial
        fields = [
            "id",
            "user",
            "user_name",
            "user_email", 
            "user_role",
            "county_department",
            "county_department_name",
            "county_name",
            "department_name",
            "position",
            "is_head",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def validate(self, attrs):
        # Ensure only one head official per county department
        county_department = attrs.get("county_department")
        is_head = attrs.get("is_head", False)
        user = attrs.get("user")
        
        # Exclude current instance if updating
        instance = getattr(self, 'instance', None)
        
        # Check if user is already assigned to any department
        if instance:
            existing_user_assignments = DepartmentOfficial.objects.filter(
                user=user
            ).exclude(id=instance.id)
        else:
            existing_user_assignments = DepartmentOfficial.objects.filter(user=user)
            
        if existing_user_assignments.exists():
            raise serializers.ValidationError(
                f"This user is already assigned to a department."
            )
        
        # Check for head official uniqueness
        if is_head:
            if instance:
                existing_head = DepartmentOfficial.objects.filter(
                    county_department=county_department, 
                    is_head=True
                ).exclude(id=instance.id)
            else:
                existing_head = DepartmentOfficial.objects.filter(
                    county_department=county_department, 
                    is_head=True
                )
                
            if existing_head.exists():
                raise serializers.ValidationError(
                    f"There is already a head official for this department in {county_department.county.name}."
                )
        
        return attrs

    def to_representation(self, instance):
        """Custom representation to include nested data"""
        representation = super().to_representation(instance)
        # Include full user and county department objects for frontend
        representation['user_data'] = {
            'id': instance.user.id,
            'email': instance.user.email,
            'full_name': instance.user.get_full_name(),
            'role': instance.user.role,
            'phone_number': instance.user.phone_number
        }
        representation['county_department_data'] = {
            'id': instance.county_department.id,
            'county': instance.county_department.county.name,
            'department': instance.county_department.department.name,
            'email': instance.county_department.email,
            'phone_number': instance.county_department.phone_number
        }
        return representation


# ============================================================
#   DEPARTMENT OFFICIAL MINIMAL SERIALIZER (For dropdowns)
# ============================================================
class DepartmentOfficialMinimalSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    department_name = serializers.CharField(source='county_department.department.name', read_only=True)
    county_name = serializers.CharField(source='county_department.county.name', read_only=True)

    class Meta:
        model = DepartmentOfficial
        fields = [
            "id",
            "user_name",
            "department_name",
            "county_name",
            "position",
            "is_head"
        ]