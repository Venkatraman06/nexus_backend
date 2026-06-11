"""
Assign realm roles (permissions) to Keycloak groups from role_permissions.json.

Usage:
    python manage.py create_permissions          # push permission catalog first
    python manage.py assign_role_permissions     # map groups → permissions
    python manage.py assign_role_permissions --dry-run
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Assign permissions to Keycloak groups (roles) from role_permissions.json"

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument(
            "--group",
            help="Only assign for this Keycloak group name (e.g. 'Project Manager')",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        only_group = options.get("group")

        role_file = Path(settings.BASE_DIR) / "role_permissions.json"
        perm_file = Path(settings.BASE_DIR) / "permissions.json"

        if not role_file.exists():
            self.stderr.write(self.style.ERROR(f"role_permissions.json not found at {role_file}"))
            return

        with role_file.open(encoding="utf-8") as f:
            role_map: dict[str, list[str]] = json.load(f)

        with perm_file.open(encoding="utf-8") as f:
            all_perms = [p["name"] for p in json.load(f)]

        if only_group:
            if only_group not in role_map:
                self.stderr.write(self.style.ERROR(f"Group not in role_permissions.json: {only_group}"))
                return
            role_map = {only_group: role_map[only_group]}

        if dry_run:
            for group_name, perms in role_map.items():
                resolved = all_perms if perms == ["*"] else perms
                self.stdout.write(f"[dry-run] {group_name}: {len(resolved)} permission(s)")
            return

        from packages.keycloak.services import KeycloakService

        svc = KeycloakService()
        groups = self._flatten_groups(svc.get_groups())
        groups_by_name = {g["name"]: g["id"] for g in groups if g.get("name")}

        assigned_groups = updated = skipped = 0

        for group_name, perm_names in role_map.items():
            group_id = groups_by_name.get(group_name)
            if not group_id:
                self.stdout.write(self.style.WARNING(f"  [SKIP] Keycloak group not found: {group_name}"))
                skipped += 1
                continue

            target_names = set(all_perms) if perm_names == ["*"] else set(perm_names)
            roles = [svc.keycloak_admin.get_realm_role(n) for n in sorted(target_names)]
            svc.update_group_permission(group_id, roles)
            assigned_groups += 1
            updated += len(target_names)
            self.stdout.write(self.style.SUCCESS(
                f"  Assigned {len(target_names)} permission(s) → {group_name}"
            ))

        self.stdout.write(self.style.SUCCESS(
            f"\nDone. Groups updated: {assigned_groups}, skipped: {skipped}, "
            f"permissions assigned: {updated}"
        ))

    @staticmethod
    def _flatten_groups(groups: list) -> list[dict]:
        flat: list[dict] = []

        def walk(items):
            for g in items or []:
                flat.append(g)
                walk(g.get("subGroups") or [])

        walk(groups)
        return flat
