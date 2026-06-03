"""
Permission catalog — runtime source of truth is Keycloak realm roles.

Aligned with impiger_moderor_iam:
  - GET permissions: realm roles with attributes.category / attributes.product
  - Group detail: all roles grouped by category, with assigned flag per group

permissions.json is only used to *seed* Keycloak (manage.py create_permissions);
it is not used to build the role-management UI catalog.
"""
from __future__ import annotations

import logging
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

PMT_PERMISSION_PRODUCT = getattr(settings, "PMT_PERMISSION_PRODUCT", "pmt")
PMT_PERMISSION_PREFIX = "pmt."

CACHE_KEY = "pmt:keycloak:permission_roles"
CACHE_TTL = getattr(settings, "PMT_PERMISSIONS_CACHE_TTL", 300)

CATEGORY_ORDER = [
    "Dashboard",
    "Master",
    "Role",
    "HRMS",
    "Policy Document",
    "Project MS",
]


def _kc_service():
    from packages.keycloak.services import KeycloakService
    return KeycloakService()


def _attr_first(attrs: dict | None, key: str) -> str | None:
    if not attrs:
        return None
    val = attrs.get(key)
    if isinstance(val, list) and val:
        return val[0] or None
    if isinstance(val, str):
        return val
    return None


def is_pmt_permission(role: dict) -> bool:
    name = role.get("name") or ""
    if name.startswith(PMT_PERMISSION_PREFIX):
        return True
    product = _attr_first(role.get("attributes"), "product")
    return product == PMT_PERMISSION_PRODUCT


def parse_keycloak_role(role: dict) -> dict | None:
    """Map a Keycloak realm role to a normalized permission dict."""
    if not is_pmt_permission(role):
        return None
    attrs = role.get("attributes") or {}
    return {
        "id": role.get("id"),
        "name": role["name"],
        "description": role.get("description") or "",
        "category": _attr_first(attrs, "category") or "Uncategorized",
        "product": _attr_first(attrs, "product") or PMT_PERMISSION_PRODUCT,
    }


def invalidate_permission_catalog_cache() -> None:
    cache.delete(CACHE_KEY)


def fetch_keycloak_roles(*, use_cache: bool = True) -> list[dict]:
    """Raw realm roles from Keycloak (brief_representation=False)."""
    if use_cache:
        cached = cache.get(CACHE_KEY)
        if cached is not None:
            return cached

    roles = _kc_service().get_permissions()
    if use_cache:
        cache.set(CACHE_KEY, roles, CACHE_TTL)
    return roles


def fetch_pmt_permissions_from_keycloak(*, use_cache: bool = True) -> list[dict]:
    """All PMT permissions parsed from Keycloak."""
    parsed: list[dict] = []
    for role in fetch_keycloak_roles(use_cache=use_cache):
        item = parse_keycloak_role(role)
        if item:
            parsed.append(item)
    return parsed


def get_all_pmt_permission_names(*, use_cache: bool = True) -> list[str]:
    return [p["name"] for p in fetch_pmt_permissions_from_keycloak(use_cache=use_cache)]


def build_permission_catalog(
    assigned_names: set[str] | frozenset[str] | None = None,
    *,
    use_cache: bool = True,
) -> list[dict]:
    """
    Permissions grouped by Keycloak attribute ``category`` for role-management UI.

    When *assigned_names* is provided, each permission includes ``assigned: bool``.
    """
    grouped: dict[str, list[dict]] = {}
    assigned = set(assigned_names) if assigned_names is not None else None

    for p in fetch_pmt_permissions_from_keycloak(use_cache=use_cache):
        cat = p["category"]
        entry: dict = {
            "name": p["name"],
            "description": p["description"],
            "label": p["description"] or p["name"],
        }
        if p.get("id"):
            entry["id"] = p["id"]
        if assigned is not None:
            entry["assigned"] = p["name"] in assigned
        grouped.setdefault(cat, []).append(entry)

    order = {c: i for i, c in enumerate(CATEGORY_ORDER)}
    catalog = []
    for cat in sorted(grouped.keys(), key=lambda c: (order.get(c, 999), c)):
        perms = sorted(grouped[cat], key=lambda x: x["name"])
        catalog.append({
            "category": cat,
            "category_label": cat,
            "permissions": perms,
        })
    return catalog


# Backward-compatible alias used across the codebase
def all_permission_names() -> list[str]:
    return get_all_pmt_permission_names()


@lru_cache(maxsize=1)
def _fallback_names_from_json() -> tuple[str, ...]:
    """Offline fallback when Keycloak is unreachable (dev only)."""
    import json
    from pathlib import Path
    path = Path(settings.BASE_DIR) / "permissions.json"
    if not path.exists():
        return ()
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return tuple(
        p["name"] for p in data
        if isinstance(p, dict) and p.get("name", "").startswith(PMT_PERMISSION_PREFIX)
    )


def get_all_pmt_permission_names_safe() -> list[str]:
    """Keycloak first; fall back to permissions.json names if KC is down."""
    try:
        names = get_all_pmt_permission_names()
        if names:
            return names
    except Exception as exc:
        logger.warning("Keycloak permission fetch failed, using JSON fallback: %s", exc)
    return list(_fallback_names_from_json())

