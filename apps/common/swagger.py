"""
drf-spectacular helpers:
  - postprocess_schema_tags: replaces the fallback "v1" tag
  - KeycloakAuthenticationScheme: registers Bearer token for Swagger UI
"""
from drf_spectacular.extensions import OpenApiAuthenticationExtension


class KeycloakAuthenticationScheme(OpenApiAuthenticationExtension):
    """Tell drf-spectacular that KeycloakAuthentication uses Bearer token."""
    target_class = "apps.common.authentication.KeycloakAuthentication"
    name = "BearerAuth"

    def get_security_definition(self, auto_schema):
        return {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT",
            "description": "Keycloak access token. Paste as: Bearer <token>",
        }

_PATH_TAG_MAP = {
    "employees":             "auth",
    "employee-certificates": "auth",
    "permissions":           "auth",
    "clients":               "projects",
    "projects":              "projects",
    "epics":                 "projects",
    "stories":               "projects",
    "workitems":             "workitems",
    "work-items":            "workitems",
    "worklogs":              "workitems",
    "work-logs":             "workitems",
    "allocations":           "allocation",
    "timesheets":            "timesheets",
    "dashboard":             "dashboard",
    "reports":               "reports",
    "workflow":              "workflow",
    "states":                "workflow",
    "transitions":           "workflow",
}


def _tag_from_path(path: str) -> str | None:
    """Return the tag for a path like /pmt/api/v1/<segment>/..."""
    parts = [p for p in path.split("/") if p]
    try:
        v1_idx = parts.index("v1")
        segment = parts[v1_idx + 1] if v1_idx + 1 < len(parts) else None
        return _PATH_TAG_MAP.get(segment)
    except ValueError:
        return None


def postprocess_schema_tags(result, generator, request, public):
    """
    drf-spectacular POSTPROCESSING_HOOK.
    Replaces generic "v1" tags with semantic ones derived from the URL structure.
    """
    for path, path_item in result.get("paths", {}).items():
        tag = _tag_from_path(path)
        if not tag:
            continue
        for method_data in path_item.values():
            if not isinstance(method_data, dict):
                continue
            current_tags = method_data.get("tags", [])
            # Only override if it's the fallback "v1" tag or missing
            if current_tags == ["v1"] or not current_tags:
                method_data["tags"] = [tag]

    return result
