"""
API views for Keycloak permission management.

POST /api/v1/permissions/create/   — push permissions.json to Keycloak (admin only)
POST /api/v1/permissions/sync/     — invalidate & re-fetch permission cache for a user
"""
import json
from pathlib import Path

from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticated
from apps.common.permissions_catalog import invalidate_permission_catalog_cache


class PermissionCreateView(APIView):
    """
    Push all permissions from permissions.json to Keycloak as realm roles
    (with category/product attributes).
    Requires pmt.permission.create (staff bypass applies).
    """
    permission_classes = [IsAuthenticated]

    def has_permission(self, request, view):
        perms = getattr(request, "user_permissions", [])
        return request.user.is_staff or "pmt.permission.create" in perms

    def post(self, request):
        perm_file = Path(settings.BASE_DIR) / "permissions.json"
        if not perm_file.exists():
            return Response(
                {"error": "permissions.json not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        with perm_file.open(encoding="utf-8") as f:
            permissions: list[dict] = json.load(f)

        try:
            from packages.keycloak.services import KeycloakService
            svc = KeycloakService()
            existing = {r["name"] for r in svc.get_permissions()}
            created, skipped, updated = [], [], []

            for perm in permissions:
                name = perm["name"]
                payload = svc.permission_role_payload(
                    name,
                    perm.get("description", ""),
                    category=perm.get("category", ""),
                )
                if name in existing:
                    svc.update_permission(name, payload)
                    updated.append(name)
                else:
                    svc.create_permissions(payload)
                    created.append(name)

            invalidate_permission_catalog_cache()
            return Response({
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "total": len(permissions),
            })
        except Exception as exc:
            return Response(
                {"error": str(exc)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class PermissionSyncView(APIView):
    """
    Invalidate and re-fetch Keycloak permission cache for a specific user.

    Body: { "user_id": "<keycloak-uuid>" }   (optional — defaults to current user)
    Requires pmt.permission.sync to refresh another user; own cache is always allowed.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request):
        from packages.keycloak.permissions import PermissionResolver, invalidate_permissions_cache

        target_user_id: str = (
            request.data.get("user_id") or request.keycloak_user_id
        )
        own_request = target_user_id == getattr(request, "keycloak_user_id", None)

        if not own_request:
            perms = getattr(request, "user_permissions", [])
            if not (request.user.is_staff or "pmt.permission.sync" in perms):
                return Response(
                    {"error": "You do not have permission to sync other users"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        invalidate_permissions_cache(target_user_id)
        invalidate_permission_catalog_cache()
        refreshed = PermissionResolver().resolve_permissions(target_user_id)

        return Response({
            "user_id": target_user_id,
            "permissions": refreshed,
            "count": len(refreshed),
        })
