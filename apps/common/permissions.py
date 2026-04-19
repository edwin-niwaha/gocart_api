from rest_framework.permissions import BasePermission

class IsTenantAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        user = request.user
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "user_type", None) in ["tenant_admin", "manager"]
        )