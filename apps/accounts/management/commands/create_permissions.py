"""
Management command: python manage.py create_permissions

Reads permissions.json and creates/updates realm roles in Keycloak with
category and product attributes (same model as impiger_moderor_iam).
"""
import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Push permissions from permissions.json to Keycloak as realm roles"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without making Keycloak calls",
        )
        parser.add_argument(
            "--update",
            action="store_true",
            help="Update existing roles (description + attributes)",
        )

    def handle(self, *args, **options):
        dry_run: bool = options["dry_run"]
        update: bool = options["update"]
        perm_file = Path(settings.BASE_DIR) / "permissions.json"

        if not perm_file.exists():
            self.stderr.write(self.style.ERROR(f"permissions.json not found at {perm_file}"))
            return

        with perm_file.open(encoding="utf-8") as f:
            permissions: list[dict] = json.load(f)

        self.stdout.write(f"Found {len(permissions)} permissions to sync")

        if dry_run:
            for p in permissions:
                cat = p.get("category", "")
                self.stdout.write(f"  [dry-run] {p['name']} category={cat}")
            return

        from apps.common.permissions_catalog import invalidate_permission_catalog_cache
        from packages.keycloak.services import KeycloakService

        svc = KeycloakService()
        existing = {r["name"] for r in svc.get_permissions()}
        created = updated = skipped = 0

        for perm in permissions:
            name = perm["name"]
            payload = svc.permission_role_payload(
                name,
                perm.get("description", ""),
                category=perm.get("category", ""),
            )
            try:
                if name in existing:
                    if update:
                        svc.update_permission(name, payload)
                        updated += 1
                        self.stdout.write(self.style.WARNING(f"  updated: {name}"))
                    else:
                        skipped += 1
                        self.stdout.write(f"  skip (exists): {name}")
                else:
                    svc.create_permissions(payload)
                    created += 1
                    self.stdout.write(self.style.SUCCESS(f"  created: {name}"))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f"  FAILED {name}: {exc}"))

        invalidate_permission_catalog_cache()
        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created: {created}, Updated: {updated}, Skipped: {skipped}"
            )
        )
