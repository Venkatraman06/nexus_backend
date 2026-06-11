from django.core.management.base import BaseCommand

from apps.accounts.services import KeycloakSyncService


class Command(BaseCommand):
    help = "Sync all employees from Keycloak into the local database"

    def handle(self, *args, **options):
        self.stdout.write("Starting Keycloak employee sync...")
        try:
            result = KeycloakSyncService().sync_all()
            self.stdout.write(self.style.SUCCESS(
                f"Sync complete — created: {result['created']}, "
                f"updated: {result['updated']}, skipped: {result['skipped']}, "
                f"errors: {result['errors']}"
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Sync failed: {exc}"))
