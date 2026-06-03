from __future__ import annotations

import logging
from typing import List

from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_TTL = 600  # 10 minutes


def _cache_key(user_id: str) -> str:
    return f"kc:perms:{user_id}"


def invalidate_permissions_cache(user_id: str) -> None:
    if user_id:
        cache.delete(_cache_key(user_id))


class PermissionResolver:
    """
    Resolves a Keycloak user's effective realm-role permissions.

    - Permissions are fetched from Keycloak Admin API on first request.
    - Cached in Redis for 10 minutes per user.
    - Call `invalidate_permissions_cache(user_id)` to force refresh.
    """

    def resolve_permissions(self, user_id: str) -> List[str]:
        if not user_id:
            return []

        key = _cache_key(user_id)
        cached = cache.get(key)
        if isinstance(cached, list):
            return cached

        try:
            from packages.keycloak.services import KeycloakService
            permissions = KeycloakService().get_effective_user_permissions(user_id)
            result = list(_dedupe(permissions))
            cache.set(key, result, timeout=_CACHE_TTL)
            return result
        except Exception as exc:
            logger.error("PermissionResolver failed for %s: %s", user_id, exc)
            return []


def _dedupe(values):
    seen: set[str] = set()
    for v in values:
        if isinstance(v, str) and v not in seen:
            seen.add(v)
            yield v
