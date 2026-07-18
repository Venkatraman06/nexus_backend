from rest_framework.permissions import BasePermission


class IsAuthenticated(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_staff)


class IsPMO(BasePermission):
    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        return getattr(request.user, "is_pmo", False) or request.user.is_staff


class IsOwnerOrAdmin(BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return getattr(obj, "created_by", None) == request.user


class HasKeycloakPermission(BasePermission):
    """
    Permission class driven by `view.PERMISSION_MAP`.

    PERMISSION_MAP maps DRF action names to required Keycloak realm-role names:

        PERMISSION_MAP = {
            "list":             "pmt.project.view",
            "create":           "pmt.project.create",
            "retrieve":         "pmt.project.view",
            "update":           "pmt.project.update",
            "partial_update":   "pmt.project.update",
            "destroy":          "pmt.project.delete",
            "transition":       "pmt.project.update",
        }

    Admins (is_staff / is_superuser) bypass the Keycloak permission check.
    For all other users the resolved permissions list
    (attached by KeycloakAuthentication as `request.user_permissions`) must
    contain the required role.

    If no PERMISSION_MAP is defined on the view the class falls back to
    requiring authentication only.
    """

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False

        if request.user.is_staff or getattr(request.user, "is_superuser", False):
            return True

        user_perms: list = getattr(request, "user_permissions", [])

        # APIView: single required_permission attribute
        required_permission = getattr(view, "required_permission", None)
        if required_permission:
            return required_permission in user_perms

        # ViewSet: PERMISSION_MAP keyed by action name
        permission_map: dict = getattr(view, "PERMISSION_MAP", {})
        if not permission_map:
            return True  # no map → authenticated users are allowed

        action = getattr(view, "action", None)
        required = permission_map.get(action)
        if required is None:
            return True  # action not in map → allow

        return required in user_perms

    def has_object_permission(self, request, view, obj):
        return self.has_permission(request, view)
