from django.core.management.base import BaseCommand

from apps.accounts.tasks import run_sync_all_employees, sync_employees_task


class Command(BaseCommand):
    help = "Sync all employees from Keycloak into the local database"

    def add_arguments(self, parser):
        parser.add_argument(
            "--async",
            action="store_true",
            dest="run_async",
            help="Queue Celery task instead of running synchronously",
        )

    def handle(self, *args, **options):
        if options["run_async"]:
            result = sync_employees_task.delay()
            self.stdout.write(self.style.SUCCESS(f"Queued sync_employees task: {result.id}"))
            return

        self.stdout.write("Starting Keycloak employee sync...")
        try:
            result = run_sync_all_employees()
            self.stdout.write(self.style.SUCCESS(
                f"Sync complete — created: {result['created']}, "
                f"updated: {result['updated']}, skipped: {result['skipped']}, "
                f"errors: {result['errors']}"
            ))
        except Exception as exc:
            self.stderr.write(self.style.ERROR(f"Sync failed: {exc}"))
