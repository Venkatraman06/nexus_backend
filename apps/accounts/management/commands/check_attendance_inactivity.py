from datetime import date, timedelta
from django.core.management.base import BaseCommand
from apps.accounts.models import Employee
from apps.common.constants import EmployeeStatus
from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.master.models import Holiday

class Command(BaseCommand):
    help = "Check employees who have not marked attendance for 5 consecutive working days and mark them inactive."

    def handle(self, *args, **options):
        self.stdout.write("Checking consecutive attendance inactivity...")
        
        # 1. Get the last 5 working days (excluding weekends and holidays)
        today = date.today()
        working_days = []
        current = today
        # We look back up to 30 calendar days to find 5 working days
        limit = 30
        while len(working_days) < 5 and limit > 0:
            is_weekend = current.weekday() >= 5
            is_holiday = Holiday.objects.filter(date=current, is_active=True).exists()
            if not is_weekend and not is_holiday:
                working_days.append(current)
            current -= timedelta(days=1)
            limit -= 1
            
        if len(working_days) < 5:
            self.stdout.write(self.style.WARNING("Could not find 5 working days in the last 30 days. Skipping check."))
            return
            
        self.stdout.write(f"Last 5 working days to check: {[wd.isoformat() for wd in working_days]}")
        
        # 2. Find all active employees
        active_employees = Employee.objects.filter(status=EmployeeStatus.ACTIVE, is_deleted=False)
        marked_inactive_count = 0
        
        for emp in active_employees:
            # Only check working days that are >= employee joining_date and >= employee creation date
            emp_start_date = emp.joining_date or emp.created_at.date()
            valid_wd = [wd for wd in working_days if wd >= emp_start_date]
            
            # If the employee joined less than 5 working days ago, we cannot check 5 consecutive days yet
            if len(valid_wd) < 5:
                continue
                
            # Check if this employee has marked attendance on ANY of these 5 working days.
            # Marked attendance means an AttendanceRecord exists with status PRESENT, HALF_DAY, or WFH,
            # and a non-null check_in time.
            marked_any = AttendanceRecord.objects.filter(
                employee=emp,
                date__in=valid_wd,
                status__in=[AttendanceStatus.PRESENT, AttendanceStatus.HALF_DAY, AttendanceStatus.WFH],
                check_in__isnull=False
            ).exists()
            
            if not marked_any:
                self.stdout.write(self.style.WARNING(
                    f"Employee {emp.full_name} ({emp.employee_code}) has not marked attendance for 5 consecutive working days. Marking INACTIVE."
                ))
                emp.status = EmployeeStatus.INACTIVE
                emp.save()
                marked_inactive_count += 1
                
        self.stdout.write(self.style.SUCCESS(f"Check complete. Marked {marked_inactive_count} employees inactive."))
