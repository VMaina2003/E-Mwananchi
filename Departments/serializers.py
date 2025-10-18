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