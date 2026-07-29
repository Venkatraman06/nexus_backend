from decimal import Decimal
from django.core.management.base import BaseCommand
from apps.accounts.models import Employee
from apps.master.models import LeaveType
from apps.attendance.models import LeaveBalance


class Command(BaseCommand):
    help = "Set Casual Leave = 3.5 days and Sick Leave = 2.5 days for employees for the financial year."

    def add_arguments(self, parser):
        parser.add_argument("--user", type=str, help="Specific employee username or code (optional).")
        parser.add_argument("--casual", type=float, default=3.5, help="Casual leave total days (default: 3.5).")
        parser.add_argument("--sick", type=float, default=2.5, help="Sick leave total days (default: 2.5).")
        parser.add_argument("--year", type=int, default=2026, help="Target year (default: 2026).")

    def handle(self, *args, **options):
        casual_days = Decimal(str(options["casual"]))
        sick_days = Decimal(str(options["sick"]))
        target_year = options["year"]
        user_param = options.get("user")

        # 1. Update/Ensure LeaveType defaults
        cl_type, _ = LeaveType.objects.get_or_create(
            code="CL",
            defaults={"name": "Casual Leave", "max_days": casual_days, "is_paid": True, "color": "#1677ff"}
        )
        if cl_type.max_days != casual_days:
            cl_type.max_days = casual_days
            cl_type.save(update_fields=["max_days"])

        sl_type, _ = LeaveType.objects.get_or_create(
            code="SL",
            defaults={"name": "Sick Leave", "max_days": sick_days, "is_paid": True, "color": "#ef4444"}
        )
        if sl_type.max_days != sick_days:
            sl_type.max_days = sick_days
            sl_type.save(update_fields=["max_days"])

        # 2. Employees query
        employees = Employee.objects.filter(is_deleted=False, is_active=True)
        if user_param:
            employees = employees.filter(
                username__iexact=user_param
            ) | Employee.objects.filter(
                employee_code__iexact=user_param, is_deleted=False
            )

        updated_count = 0
        years_to_update = list({target_year, 2025, 2026})

        for emp in employees:
            for y in years_to_update:
                # Casual Leave
                bal_cl, _ = LeaveBalance.objects.get_or_create(
                    employee=emp, leave_type=cl_type, year=y,
                    defaults={"total_days": casual_days, "used_days": 0}
                )
                if bal_cl.total_days != casual_days:
                    bal_cl.total_days = casual_days
                    bal_cl.save(update_fields=["total_days"])

                # Sick Leave
                bal_sl, _ = LeaveBalance.objects.get_or_create(
                    employee=emp, leave_type=sl_type, year=y,
                    defaults={"total_days": sick_days, "used_days": 0}
                )
                if bal_sl.total_days != sick_days:
                    bal_sl.total_days = sick_days
                    bal_sl.save(update_fields=["total_days"])

                updated_count += 2

        self.stdout.write(
            self.style.SUCCESS(
                f"Successfully set Casual Leave = {casual_days}d and Sick Leave = {sick_days}d "
                f"for {employees.count()} employee(s) across years {years_to_update}."
            )
        )
