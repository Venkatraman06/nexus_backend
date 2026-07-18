import calendar
from datetime import date
from decimal import Decimal

from django.db.models import Q, Sum

from apps.common.constants import DAILY_HOURS, OVER_ALLOCATION_THRESHOLD
from .models import Allocation


class CapacityService:
    @staticmethod
    def get_working_days(year: int, month: int) -> int:
        _, last_day = calendar.monthrange(year, month)
        working = 0
        for day in range(1, last_day + 1):
            if date(year, month, day).weekday() < 5:
                working += 1
        return working

    @staticmethod
    def employee_monthly_capacity(employee, year: int, month: int) -> dict:
        from apps.workitems.models import WorkLog

        working_days = CapacityService.get_working_days(year, month)
        total_capacity = working_days * DAILY_HOURS

        first_day = date(year, month, 1)
        _, last_day_num = calendar.monthrange(year, month)
        last_day = date(year, month, last_day_num)

        # Active allocations during this month
        allocations = Allocation.objects.filter(
            employee=employee,
            is_deleted=False,
            start_date__lte=last_day,
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=first_day))

        total_allocation_pct = float(
            allocations.aggregate(total=Sum("allocation_percentage"))["total"] or 0
        )
        allocated_hours = (total_allocation_pct / 100) * total_capacity
        is_over_allocated = total_allocation_pct > OVER_ALLOCATION_THRESHOLD

        # Logged hours in this month
        logs = WorkLog.objects.filter(
            employee=employee,
            is_deleted=False,
            log_date__year=year,
            log_date__month=month,
        )
        total_logged = float(logs.aggregate(t=Sum("hours"))["t"] or 0)
        billable_logged = float(logs.filter(is_billable=True).aggregate(t=Sum("hours"))["t"] or 0)

        utilization_pct = (total_logged / allocated_hours * 100) if allocated_hours > 0 else 0
        billing_utilization_pct = (billable_logged / total_logged * 100) if total_logged > 0 else 0

        return {
            "employee_id": employee.id,
            "employee_name": employee.full_name,
            "month": f"{year}-{month:02d}",
            "working_days": working_days,
            "total_capacity_hours": total_capacity,
            "allocated_hours": round(allocated_hours, 2),
            "logged_hours": round(total_logged, 2),
            "utilization_percent": round(utilization_pct, 2),
            "billing_utilization_percent": round(billing_utilization_pct, 2),
            "allocation_percent": round(total_allocation_pct, 2),
            "is_over_allocated": is_over_allocated,
        }
