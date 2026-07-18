import json
import logging

from django.conf import settings
from keycloak import KeycloakAdmin, KeycloakOpenID

logger = logging.getLogger(__name__)


class KeycloakService:
    def __init__(self):
        self.keycloak_admin = KeycloakAdmin(
            server_url=settings.KEYCLOAK_SERVER_URL,
            realm_name=settings.KEYCLOAK_REALM,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
            verify=True,
        )
        self.keycloak_openid = KeycloakOpenID(
            server_url=settings.KEYCLOAK_SERVER_URL,
            realm_name=settings.KEYCLOAK_REALM,
            client_id=settings.KEYCLOAK_CLIENT_ID,
            client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
        )

    # ------------------------------------------------------------------ #
    # Permissions / realm roles
    # ------------------------------------------------------------------ #

    def get_permissions(self):
        realm_roles = self.keycloak_admin.get_realm_roles(
            brief_representation=False, search_text=""
        )
        return [
            role for role in realm_roles
            if role["name"] not in ["offline_access", "uma_authorization"]
            and not role["name"].startswith("default-roles")
        ]

    def create_permissions(self, payload):
        return self.keycloak_admin.create_realm_role(payload=payload, skip_exists=True)

    def update_permission(self, role_name, payload):
        return self.keycloak_admin.update_realm_role(role_name=role_name, payload=payload)

    @staticmethod
    def permission_role_payload(
        name: str,
        description: str = "",
        *,
        category: str = "",
        product: str | None = None,
    ) -> dict:
        """Build Keycloak realm-role payload with category/product attributes (IAM model)."""
        from django.conf import settings as django_settings
        prod = product or getattr(django_settings, "PMT_PERMISSION_PRODUCT", "pmt")
        attrs: dict[str, list[str]] = {}
        if category:
            attrs["category"] = [category]
        if prod:
            attrs["product"] = [prod]
        payload: dict = {"name": name, "description": description or ""}
        if attrs:
            payload["attributes"] = attrs
        return payload

    # ------------------------------------------------------------------ #
    # Groups
    # ------------------------------------------------------------------ #

    def get_groups(self):
        return self.keycloak_admin.get_groups()

    def get_group(self, group_id):
        return self.keycloak_admin.get_group(group_id)

    def get_group_permission(self, group_id):
        return self.keycloak_admin.get_group_realm_roles(
            group_id, brief_representation=False
        )

    def assign_group_permission(self, group_id, permissions):
        return self.keycloak_admin.assign_group_realm_roles(group_id, permissions)

    def update_group_permission(self, group_id, permissions):
        current_roles = self.get_group_permission(group_id)
        current_names = {r["name"] for r in current_roles}
        target_names = {r["name"] for r in permissions}

        to_add = [self.keycloak_admin.get_realm_role(n) for n in (target_names - current_names)]
        to_remove = [self.keycloak_admin.get_realm_role(n) for n in (current_names - target_names)]

        if to_remove:
            self.keycloak_admin.delete_group_realm_roles(group_id, to_remove)
        if to_add:
            self.keycloak_admin.assign_group_realm_roles(group_id, to_add)

    # ------------------------------------------------------------------ #
    # Users
    # ------------------------------------------------------------------ #

    def get_users(self, **kwargs):
        return self.keycloak_admin.get_users(query=kwargs)

    def get_user(self, user_id):
        return self.keycloak_admin.get_user(user_id)

    def get_user_group(self, user_id):
        return self.keycloak_admin.get_user_groups(user_id)

    def create_user(self, payload):
        return self.keycloak_admin.create_user(payload, exist_ok=False)

    def update_user(self, user_id, payload):
        return self.keycloak_admin.update_user(user_id=user_id, payload=payload)

    # ------------------------------------------------------------------ #
    # Effective permission resolution
    # ------------------------------------------------------------------ #

    @staticmethod
    def _filter_permission_names(roles):
        return [
            role.get("name")
            for role in (roles or [])
            if isinstance(role, dict)
            and role.get("name")
            and role["name"] not in ["offline_access", "uma_authorization"]
            and not role["name"].startswith("default-roles")
        ]

    def _get_user_group_permissions(self, user_id: str):
        groups = self.get_user_group(user_id) or []
        all_names: list[str] = []
        for grp in groups:
            group_id = grp.get("id") if isinstance(grp, dict) else None
            if not group_id:
                continue
            group_roles = self.get_group_permission(group_id)
            all_names.extend(self._filter_permission_names(group_roles))

        seen: set[str] = set()
        uniq: list[str] = []
        for n in all_names:
            if n not in seen:
                seen.add(n)
                uniq.append(n)
        return uniq

    def get_effective_user_permissions(self, user_id: str):
        """
        Resolve effective realm roles for a user.

        1. Try composite role-mappings endpoint.
        2. On 403/404 fall back to group-based lookup.
        3. If composite returns empty → also fall back.
        """
        try:
            realm = settings.KEYCLOAK_REALM
            resp = self.keycloak_admin.connection.raw_get(
                f"admin/realms/{realm}/users/{user_id}/role-mappings/realm/composite"
            )

            if resp.status_code in (403, 404):
                logger.warning(
                    "Composite role-mappings returned %s for user %s; falling back to group-based",
                    resp.status_code, user_id,
                )
                return self._get_user_group_permissions(user_id)

            if resp.status_code != 200:
                raise RuntimeError(
                    f"Keycloak effective-permissions fetch failed (status={resp.status_code})"
                )

            roles = json.loads(resp.content or "[]")
            names = self._filter_permission_names(roles)
            return names or self._get_user_group_permissions(user_id)

        except Exception as exc:
            logger.error("get_effective_user_permissions failed for %s: %s", user_id, exc)
            raise
