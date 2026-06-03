import logging
from django.conf import settings
from .models import Employee
from .group_config import resolve_group_flags

logger = logging.getLogger(__name__)

# Usernames that belong to Keycloak itself — never sync these as employees
SYSTEM_USERNAMES = {"admin", "local-admin", "service-account"}


def _get_keycloak_admin():
    from keycloak import KeycloakAdmin
    return KeycloakAdmin(
        server_url=settings.KEYCLOAK_SERVER_URL,
        realm_name=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
        verify=True,
    )


class KeycloakSyncService:
    def __init__(self):
        self._admin = None
        self._group_map: dict[str, str] = {}   # group_id → group_name

    @property
    def admin(self):
        if self._admin is None:
            self._admin = _get_keycloak_admin()
        return self._admin

    # ── Group helpers ─────────────────────────────────────────────────────────

    def _load_groups(self):
        """Cache realm groups as {id: name} for fast lookup."""
        try:
            groups = self.admin.get_groups()
            self._group_map = {g["id"]: g["name"] for g in groups}
        except Exception as exc:
            logger.warning("Could not load Keycloak groups: %s", exc)

    def _primary_group(self, keycloak_user_id: str) -> str:
        """Return the first group name assigned to a Keycloak user, or ''."""
        try:
            user_groups = self.admin.get_user_groups(keycloak_user_id)
            if user_groups:
                first = user_groups[0]
                return self._group_map.get(first["id"], first.get("name", ""))
        except Exception as exc:
            logger.debug("Could not get groups for user %s: %s", keycloak_user_id, exc)
        return ""

    # ── Data builders ─────────────────────────────────────────────────────────

    def _build_employee_data(self, kc_user: dict, group_name: str = "", is_new: bool = False) -> dict:
        attrs = kc_user.get("attributes", {})
        flags = resolve_group_flags(group_name)
        data = {
            "username":      kc_user.get("username", ""),
            "email":         kc_user.get("email", ""),
            "first_name":    kc_user.get("firstName", ""),
            "last_name":     kc_user.get("lastName", ""),
            "is_active":     kc_user.get("enabled", True),
            "designation":   attrs.get("designation", [""])[0] if attrs.get("designation") else "",
            "department":    attrs.get("department", [""])[0] if attrs.get("department") else "",
            "keycloak_group": group_name,
            **flags,
        }
        if is_new:
            data["keycloak_id"] = kc_user["id"]
        return data

    # ── Public API ────────────────────────────────────────────────────────────

    def sync_all(self) -> dict:
        created = updated = skipped = errors = 0

        self._load_groups()

        try:
            users = self.admin.get_users({})
            logger.info("Keycloak sync: %d users found", len(users))

            for kc_user in users:
                kc_id = kc_user.get("id")
                username = kc_user.get("username", "")

                # Skip Keycloak system accounts
                if username.lower() in SYSTEM_USERNAMES:
                    skipped += 1
                    continue

                try:
                    group_name = self._primary_group(kc_id)
                    existing = Employee.objects.filter(keycloak_id=kc_id).first()
                    data = self._build_employee_data(kc_user, group_name, is_new=(existing is None))

                    if existing is None:
                        # Auto-generate employee code for new synced users
                        data["employee_code"] = Employee.objects.generate_employee_code()
                        Employee.objects.create(**data)
                        created += 1
                    else:
                        changed = any(
                            getattr(existing, k, None) != v
                            for k, v in data.items()
                            if k != "keycloak_id"
                        )
                        if changed:
                            for k, v in data.items():
                                setattr(existing, k, v)
                            existing.save()
                            updated += 1
                        else:
                            skipped += 1

                except Exception as exc:
                    logger.error("Failed to sync user %s: %s", kc_id, exc)
                    errors += 1

        except Exception as exc:
            logger.error("Keycloak sync failed: %s", exc)
            raise

        return {"created": created, "updated": updated, "skipped": skipped, "errors": errors}

    def sync_one(self, keycloak_id: str) -> Employee:
        self._load_groups()
        kc_user = self.admin.get_user(keycloak_id)
        group_name = self._primary_group(keycloak_id)
        existing = Employee.objects.filter(keycloak_id=keycloak_id).first()
        data = self._build_employee_data(kc_user, group_name, is_new=(existing is None))

        if existing is None:
            data["employee_code"] = Employee.objects.generate_employee_code()
            return Employee.objects.create(**data)

        for k, v in data.items():
            setattr(existing, k, v)
        existing.save()
        return existing
