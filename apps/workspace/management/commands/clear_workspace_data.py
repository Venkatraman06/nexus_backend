from django.core.management.base import BaseCommand
from django.db.models import Q
from apps.accounts.models import Employee
from apps.followups.models import FollowUp
from apps.todos.models import Todo
from apps.meetings.models import Meeting


class Command(BaseCommand):
    help = "Delete all workspace data (FollowUps, Meetings, Todos) for specified employees."

    def add_arguments(self, parser):
        parser.add_argument(
            "--user",
            action="append",
            dest="users",
            help="Employee code or username to delete workspace data for (can be specified multiple times).",
        )

    def handle(self, *args, **options):
        user_list = options.get("users") or ["HIT-005", "HIT-008"]

        employees = Employee.objects.filter(
            Q(username__in=user_list) | Q(employee_code__in=user_list),
            is_deleted=False,
        )

        if not employees.exists():
            self.stdout.write(self.style.WARNING(f"No employees found for codes/usernames: {user_list}"))
            return

        emp_ids = list(employees.values_list("id", flat=True))
        emp_names = ", ".join(f"{e.full_name} ({e.employee_code})" for e in employees)
        self.stdout.write(f"Clearing workspace data for: {emp_names}")

        # 1. Followups
        fu_qs = FollowUp.objects.filter(
            Q(reporter_id__in=emp_ids) | Q(created_by_id__in=emp_ids) | Q(assignees__id__in=emp_ids)
        ).distinct()
        fu_count = fu_qs.count()
        fu_qs.delete()

        # 2. Meetings
        m_qs = Meeting.objects.filter(
            Q(reporter_id__in=emp_ids) | Q(created_by_id__in=emp_ids) | Q(assignees__id__in=emp_ids)
        ).distinct()
        m_count = m_qs.count()
        m_qs.delete()

        # 3. Todos
        todo_qs = Todo.objects.filter(
            Q(reporter_id__in=emp_ids) | Q(created_by_id__in=emp_ids) | Q(assignees__id__in=emp_ids)
        ).distinct()
        todo_count = todo_qs.count()
        todo_qs.delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully deleted {fu_count} Follow-up(s), {m_count} Meeting(s), and {todo_count} To-do(s) "
                f"for employees: {user_list}."
            )
        )
