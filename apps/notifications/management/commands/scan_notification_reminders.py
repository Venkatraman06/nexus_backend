"""Run the daily due-date / follow-up notification scan on demand."""

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Scan tickets, projects, invoices, and follow-ups; create in-app notifications."

    def handle(self, *args, **options):
        from apps.notifications.tasks import scan_due_date_reminders
        from apps.notifications.templates_registry import sync_templates

        sync_templates()
        counts = scan_due_date_reminders()
        self.stdout.write(self.style.SUCCESS(f"Notification scan complete: {counts}"))
