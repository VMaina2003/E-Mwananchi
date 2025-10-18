from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from django.shortcuts import get_object_or_404

from .models import Department, CountyDepartment, DepartmentOfficial
from .serializers import (
    DepartmentSerializer,
    CountyDepartmentSerializer,
    DepartmentOfficialSerializer,
)

# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================
class IsAdminOrSuperAdmin(permissions.BasePermission):
    """
    Allow only Admin or SuperAdmin to create, update, or delete.
    Others (County Officials, Citizens, Viewers) can only read.
    """

    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        user = request.user
        return user.is_authenticated and (user.is_admin or user.is_superadmin)


# ============================================================
#   DEPARTMENT VIEWSET
# ============================================================
class DepartmentViewSet(viewsets.ModelViewSet):
    """
    Manage the list of all departments (e.g., Health, Education, Roads).
    Only Admin/SuperAdmin can modify.
    """

    queryset = Department.objects.all().order_by("name")
    serializer_class = DepartmentSerializer
    permission_classes = [IsAdminOrSuperAdmin]


# ============================================================
#   COUNTY DEPARTMENT VIEWSET
# ============================================================
class CountyDepartmentViewSet(viewsets.ModelViewSet):
    """
    Manage departments linked to specific counties.
    Example: Health Department - Nairobi County.
    """

    queryset = CountyDepartment.objects.select_related("county", "department").all()
    serializer_class = CountyDepartmentSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        """
        Citizens, Viewers, and Officials can only view active departments.
        Admins and SuperAdmins can view all.
        """
        user = self.request.user
        queryset = super().get_queryset()
        if user.is_authenticated and (user.is_admin or user.is_superadmin):
            return queryset
        return queryset.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        """
        Allow both single and bulk creation of county departments.
        Example of bulk data:
        [
            {
                "county": "Nairobi",
                "department": "Health",
                "email": "health@nairobi.go.ke",
                "phone_number": "+254700123456",
                "office_location": "City Hall, Nairobi"
            },
            {
                "county": "Mombasa",
                "department": "Education",
                "email": "education@mombasa.go.ke",
                "phone_number": "+254701234567",
                "office_location": "Tononoka, Mombasa"
            }
        ]
        """
        data = request.data
        if isinstance(data, list):  # Handle bulk creation
            serializer = self.get_serializer(data=data, many=True)
            serializer.is_valid(raise_exception=True)
            self.perform_bulk_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return super().create(request, *args, **kwargs)

    def perform_bulk_create(self, serializer):
        """Helper to save multiple CountyDepartment records at once."""
        serializer.save()

# ============================================================
#   DEPARTMENT OFFICIAL VIEWSET
# ============================================================
class DepartmentOfficialViewSet(viewsets.ModelViewSet):
    """
    Manage assignment of officials to county departments.
    - Admin/SuperAdmin can create/update/delete
    - CountyOfficial can view only their own department
    - Citizens/Viewers can only read
    """

    queryset = DepartmentOfficial.objects.select_related("user", "county_department").all()
    serializer_class = DepartmentOfficialSerializer
    permission_classes = [IsAdminOrSuperAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.is_county_official:
            return self.queryset.filter(user=user)
        elif user.is_authenticated and (user.is_admin or user.is_superadmin):
            return self.queryset
        return DepartmentOfficial.objects.none()