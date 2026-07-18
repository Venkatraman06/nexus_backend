"""
Management command: python manage.py sync_permissions [--user <keycloak-user-id>]
                                                      [--group <group-id>]
                                                      [--invalidate-cache]

On-demand permission sync from Keycloak:
  - With --user  → fetch and re-cache that user's effective permissions
  - With --group → print that group's current realm roles
  - No args      → invalidate the Redis permission cache for ALL known employees

This is the PMT equivalent of the IAM project's PermissionResolver + sync flow.
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Sync / refresh Keycloak permissions for users and groups on-demand"

    def add_arguments(self, parser):
        parser.add_argument("--user", help="Keycloak user UUID to refresh")
        parser.add_argument("--group", help="Keycloak group UUID to inspect")
        parser.add_argument(
            "--invalidate-cache",
            action="store_true",
            help="Invalidate Redis permission cache for all employees",
        )

    def handle(self, *args, **options):
        user_id: str | None = options.get("user")
        group_id: str | None = options.get("group")
        invalidate: bool = options["invalidate_cache"]

        from packages.keycloak.services import KeycloakService
        from packages.keycloak.permissions import PermissionResolver, invalidate_permissions_cache

        svc = KeycloakService()

        if user_id:
            self.stdout.write(f"Fetching effective permissions for user {user_id} …")
            invalidate_permissions_cache(user_id)
            perms = PermissionResolver().resolve_permissions(user_id)
            self.stdout.write(self.style.SUCCESS(f"  {len(perms)} permission(s) cached:"))
            for p in perms:
                self.stdout.write(f"    {p}")
            return

        if group_id:
            self.stdout.write(f"Realm roles for group {group_id}:")
            roles = svc.get_group_permission(group_id)
            names = svc._filter_permission_names(roles)
            for n in names:
                self.stdout.write(f"  {n}")
            return

        if invalidate:
            from apps.accounts.models import Employee
            employees = Employee.objects.exclude(keycloak_id="")
            count = 0
            for emp in employees:
                invalidate_permissions_cache(emp.keycloak_id)
                count += 1
            self.stdout.write(
                self.style.SUCCESS(f"Permission cache invalidated for {count} employees.")
            )
            return

        self.stdout.write(self.style.WARNING(
            "No action specified. Use --user, --group, or --invalidate-cache."
        ))
