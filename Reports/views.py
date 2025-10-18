from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.decorators import action
from django.utils import timezone

from .models import Report, ReportImage, ReportStatusChoices
from .serializers import ReportSerializer, ReportStatusUpdateSerializer
from Authentication.models import CustomUser


# ============================================================
#   CUSTOM PERMISSIONS
# ============================================================
class IsAuthenticatedAndHasRole(permissions.BasePermission):
    """
    Allows access only to authenticated users with allowed roles.
    """

    allowed_roles = [
        CustomUser.Roles.CITIZEN,
        CustomUser.Roles.COUNTY_OFFICIAL,
        CustomUser.Roles.ADMIN,
        CustomUser.Roles.SUPERADMIN,
    ]

    def has_permission(self, request, view):
        return (
            request.user
            and request.user.is_authenticated
            and request.user.role in self.allowed_roles
        )


class IsReporterOrAdmin(permissions.BasePermission):
    """
    Allows a report to be edited/deleted only by:
    - The creator (reporter)
    - Admin or Superadmin
    """

    def has_object_permission(self, request, view, obj):
        if request.user.is_superadmin or request.user.is_admin:
            return True
        return obj.reporter == request.user


class CanUpdateStatus(permissions.BasePermission):
    """
    Allows report status updates only for:
    - County Officials
    - Admins
    - Superadmins
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False
        return request.user.role in [
            CustomUser.Roles.COUNTY_OFFICIAL,
            CustomUser.Roles.ADMIN,
            CustomUser.Roles.SUPERADMIN,
        ]
