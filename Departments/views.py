from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django_filters.rest_framework import DjangoFilterBackend
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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['name']

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def departments(self, request):
        """
        Public endpoint to get all departments.
        Used by the frontend for department selection.
        """
        departments = Department.objects.all().order_by('name')
        serializer = self.get_serializer(departments, many=True)
        return Response(serializer.data)


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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['county', 'department', 'is_active']

    def get_queryset(self):
        """
        Citizens, Viewers, and Officials can only view active departments.
        Admins and SuperAdmins can view all.
        """
        user = self.request.user
        queryset = super().get_queryset()
        
        # Filter by county if provided
        county_id = self.request.query_params.get('county')
        if county_id:
            queryset = queryset.filter(county_id=county_id)
            
        if user.is_authenticated and (user.is_admin or user.is_superadmin):
            return queryset
        return queryset.filter(is_active=True)

    def create(self, request, *args, **kwargs):
        """
        Allow both single and bulk creation of county departments.
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

    @action(detail=False, methods=['get'], permission_classes=[permissions.AllowAny])
    def active(self, request):
        """
        Get all active county departments.
        """
        county_departments = CountyDepartment.objects.filter(is_active=True).select_related('county', 'department')
        serializer = self.get_serializer(county_departments, many=True)
        return Response(serializer.data)


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
    filter_backends = [DjangoFilterBackend]
    filterset_fields = ['county_department', 'is_head']

    def get_queryset(self):
        user = self.request.user
        if user.is_authenticated and user.is_county_official:
            return self.queryset.filter(user=user)
        elif user.is_authenticated and (user.is_admin or user.is_superadmin):
            return self.queryset
        return self.queryset.filter(county_department__is_active=True)

    @action(detail=False, methods=['get'], permission_classes=[permissions.IsAuthenticated])
    def my_department(self, request):
        """
        Get the department official record for the current user.
        """
        if not request.user.is_county_official:
            return Response(
                {"detail": "Only county officials can access this endpoint."},
                status=status.HTTP_403_FORBIDDEN
            )
        
        official = get_object_or_404(DepartmentOfficial, user=request.user)
        serializer = self.get_serializer(official)
        return Response(serializer.data)