import sys
from django.core.management.base import BaseCommand
from apps.attendance.models import LeaveRequest


class Command(BaseCommand):
    help = "Delete all leave requests or soft-delete them from the database."

    def add_arguments(self, parser):
        parser.add_argument(
            '--hard',
            action='store_true',
            help='Permanently delete leave request records from the database instead of soft deleting.',
        )
        parser.add_argument(
            '--user',
            type=str,
            help='Filter deletion by employee username.',
        )

    def handle(self, *args, **options):
        hard_delete = options.get('hard', False)
        username = options.get('user')

        qs = LeaveRequest.objects.all()

        if username:
            qs = qs.filter(employee__username=username)

        count = qs.count()
        if count == 0:
            self.stdout.write(self.style.WARNING("No leave requests found matching criteria."))
            return

        if hard_delete:
            deleted_count, _ = qs.delete()
            self.stdout.write(
                self.style.SUCCESS(f"Successfully permanently deleted {deleted_count} leave request(s).")
            )
        else:
            updated_count = qs.update(is_deleted=True, is_active=False)
            self.stdout.write(
                self.style.SUCCESS(f"Successfully soft-deleted {updated_count} leave request(s).")
            )
