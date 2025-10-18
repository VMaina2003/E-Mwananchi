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