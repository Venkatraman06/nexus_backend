import os


def _csv_set(env_key: str, default: str) -> set:
    raw = os.getenv(env_key, default)
    return {g.strip().lower() for g in raw.split(",") if g.strip()}


# Groups that grant is_pmo=True — override via .env KC_PMO_GROUPS
PMO_GROUPS: set = _csv_set("KC_PMO_GROUPS", "admin,des-admin")

# Groups that grant is_manager=True — override via .env KC_MANAGER_GROUPS
MANAGER_GROUPS: set = _csv_set("KC_MANAGER_GROUPS", "admin,hr,officer")


def resolve_group_flags(group_name: str) -> dict:
    """Return {is_pmo, is_manager} derived from a Keycloak group name."""
    name = (group_name or "").strip().lower()
    return {
        "is_pmo": name in PMO_GROUPS,
        "is_manager": name in MANAGER_GROUPS,
    }
