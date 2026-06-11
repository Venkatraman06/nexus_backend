"""
Role & permission management APIs.

Keycloak groups are exposed as roles. All Keycloak Admin API calls happen
server-side via KeycloakService — the frontend never talks to Keycloak directly.
"""
from __future__ import annotations

import logging

from django.db.models import Count
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.common.permissions_catalog import (
    build_permission_catalog,
    get_all_pmt_permission_names,
    invalidate_permission_catalog_cache,
)
from .models import Employee

logger = logging.getLogger(__name__)


def _flatten_groups(groups: list) -> list[dict]:
    flat: list[dict] = []

    def walk(items):
        for g in items or []:
            flat.append({
                "id": g.get("id"),
                "name": g.get("name"),
                "path": g.get("path", ""),
            })
            walk(g.get("subGroups") or [])

    walk(groups)
    return flat


def _kc_service():
    from packages.keycloak.services import KeycloakService
    return KeycloakService()


class PermissionCatalogView(APIView):
    """GET /permissions/catalog/ — all permissions grouped by category."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {"get": "pmt.role.view"}

    def get(self, request):
        try:
            return Response({"categories": build_permission_catalog()})
        except Exception as exc:
            logger.error("PermissionCatalogView Keycloak error: %s", exc)
            return Response(
                {"error": "Unable to fetch permissions from Keycloak"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )


class RoleListView(APIView):
    """GET /roles/ — Keycloak groups as roles."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {"get": "pmt.role.view"}

    def get(self, request):
        try:
            svc = _kc_service()
            groups = _flatten_groups(svc.get_groups())
        except Exception as exc:
            logger.error("RoleListView Keycloak error: %s", exc)
            return Response(
                {"error": "Unable to fetch roles from Keycloak"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        user_counts = {
            row["keycloak_group"]: row["cnt"]
            for row in Employee.objects.filter(is_deleted=False)
            .exclude(keycloak_group="")
            .values("keycloak_group")
            .annotate(cnt=Count("id"))
        }

        roles = []
        for g in groups:
            name = g.get("name") or ""
            roles.append({
                "id": g["id"],
                "name": name,
                "path": g.get("path", ""),
                "users_assigned": user_counts.get(name, 0),
                "status": "active",
            })

        roles.sort(key=lambda r: r["name"].lower())
        return Response({"count": len(roles), "results": roles})


class RoleDetailView(APIView):
    """GET /roles/<group_id>/ — role detail + assigned permissions."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {"get": "pmt.role.view"}

    def get(self, request, group_id):
        try:
            svc = _kc_service()
            group = svc.get_group(group_id)
            assigned = svc.get_group_permission(group_id)
            assigned_names = sorted(
                r["name"] for r in assigned
                if r.get("name", "").startswith("pmt.")
            )
        except Exception as exc:
            logger.error("RoleDetailView Keycloak error: %s", exc)
            return Response(
                {"error": "Role not found or Keycloak unavailable"},
                status=status.HTTP_404_NOT_FOUND,
            )

        name = group.get("name", "")
        users_assigned = Employee.objects.filter(
            keycloak_group=name, is_deleted=False
        ).count()

        attrs = group.get("attributes") or {}
        description = ""
        if isinstance(attrs.get("description"), list) and attrs["description"]:
            description = attrs["description"][0]
        elif isinstance(attrs.get("description"), str):
            description = attrs["description"]

        try:
            categories = build_permission_catalog(frozenset(assigned_names))
        except Exception as exc:
            logger.error("RoleDetailView permission catalog error: %s", exc)
            return Response(
                {"error": "Unable to fetch permission catalog from Keycloak"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response({
            "id": group.get("id"),
            "name": name,
            "path": group.get("path", ""),
            "description": description,
            "users_assigned": users_assigned,
            "status": "active",
            "permissions": assigned_names,
            "categories": categories,
        })


class RolePermissionsUpdateView(APIView):
    """PUT /roles/<group_id>/permissions/ — sync realm roles on a Keycloak group."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {"put": "pmt.role.permission.assign", "patch": "pmt.role.permission.assign"}

    def put(self, request, group_id):
        return self._update(request, group_id)

    def patch(self, request, group_id):
        return self._update(request, group_id)

    def _update(self, request, group_id):
        names = request.data.get("permissions")
        if not isinstance(names, list):
            return Response(
                {"error": "permissions must be a list of permission names"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            valid = set(get_all_pmt_permission_names())
        except Exception as exc:
            logger.error("RolePermissionsUpdateView catalog error: %s", exc)
            return Response(
                {"error": "Unable to validate permissions against Keycloak"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        pmt_names = [n for n in names if isinstance(n, str) and n.startswith("pmt.")]
        unknown = [n for n in pmt_names if n not in valid]
        if unknown:
            return Response(
                {"error": f"Unknown permissions: {', '.join(unknown[:5])}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            svc = _kc_service()
            roles = [svc.keycloak_admin.get_realm_role(n) for n in pmt_names]
            svc.update_group_permission(group_id, roles)
            assigned = svc.get_group_permission(group_id)
            assigned_names = sorted(
                r["name"] for r in assigned if r.get("name", "").startswith("pmt.")
            )
        except Exception as exc:
            logger.error("RolePermissionsUpdateView error: %s", exc)
            return Response(
                {"error": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        invalidate_permission_catalog_cache()
        return Response({
            "message": "Role permissions updated",
            "permissions": assigned_names,
        })
