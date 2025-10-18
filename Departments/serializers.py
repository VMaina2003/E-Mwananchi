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
    county = serializers.SlugRelatedField(
        slug_field="name", queryset=County.objects.all()
    )
    department = serializers.SlugRelatedField(
        slug_field="name", queryset=Department.objects.all()
    )

    class Meta:
        model = CountyDepartment
        fields = [
            "id",
            "county",
            "department",
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
        if CountyDepartment.objects.filter(county=county, department=department).exists():
            raise serializers.ValidationError(
                f"{department.name} department already exists in {county.name}."
            )
        return attrs
    
# ============================================================
#   DEPARTMENT OFFICIAL SERIALIZER
# ============================================================
class DepartmentOfficialSerializer(serializers.ModelSerializer):
    user = serializers.SlugRelatedField(
        slug_field="email",
        queryset=User.objects.filter(role__in=["county_official", "admin", "superadmin"]),
        help_text="Assign an existing user by email (must have county_official, admin, or superadmin role)",
    )
    county_department = serializers.SlugRelatedField(
        slug_field="id", queryset=CountyDepartment.objects.all()
    )

    class Meta:
        model = DepartmentOfficial
        fields = [
            "id",
            "user",
            "county_department",
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
        if is_head and DepartmentOfficial.objects.filter(
            county_department=county_department, is_head=True
        ).exists():
            raise serializers.ValidationError(
                f"There is already a head official for {county_department}."
            )
        return attrs