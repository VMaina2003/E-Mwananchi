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
