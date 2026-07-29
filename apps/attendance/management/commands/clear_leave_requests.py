import sys
from django.core.management.base import BaseCommand
from django.db.models import Q
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
            help='Filter deletion by employee username or employee code.',
        )
        parser.add_argument(
            '--exclude-user',
            type=str,
            help='Exclude employee username or employee code from deletion.',
        )

    def handle(self, *args, **options):
        hard_delete = options.get('hard', False)
        username = options.get('user')
        exclude_user = options.get('exclude_user')

        qs = LeaveRequest.objects.all()

        if username:
            qs = qs.filter(Q(employee__username=username) | Q(employee__employee_code=username))

        if exclude_user:
            qs = qs.exclude(Q(employee__username=exclude_user) | Q(employee__employee_code=exclude_user))

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
