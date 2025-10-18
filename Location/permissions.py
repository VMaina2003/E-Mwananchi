from rest_framework import permissions


class CanManageLocationPoint(permissions.BasePermission):
    """
    Allows deletion or update of LocationPoints only by:
    - Admin
    - SuperAdmin
    - County Official
    """

    def has_permission(self, request, view):
        user = request.user

        # Read-only requests (GET, HEAD, OPTIONS) are allowed for everyone
        if request.method in permissions.SAFE_METHODS:
            return True

        # Only authenticated users with special roles can delete or modify
        if not user.is_authenticated:
            return False

        allowed_roles = ["admin", "superadmin"]
        return getattr(user, "role", None) in allowed_roles
