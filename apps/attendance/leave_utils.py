from decimal import Decimal
from datetime import date
from typing import List, Set

from django.db.models import Q

from apps.dashboard.fy_utils import current_fy_start, fy_label  # noqa: F401  (fy_label re-exported for callers)


def eligible_carry_forward_days(employee, leave_type, fy_start_year):
    """Unused days from the previous FY an employee can carry into `fy_start_year`,
    per the LeaveType's policy rule. 0 if no rule, carry_forward is off, or no prior balance."""
    from .models import LeaveBalance, LeavePolicyRule

    prev_fy = fy_start_year - 1
    rule = (
        LeavePolicyRule.objects.filter(leave_type=leave_type, effective_from__lte=prev_fy)
        .filter(Q(effective_to__gte=prev_fy) | Q(effective_to__isnull=True))
        .order_by("-effective_from")
        .first()
    )
    if not rule or not rule.carry_forward:
        return Decimal("0")

    prev_balance = LeaveBalance.objects.filter(
        employee=employee, leave_type=leave_type, year=prev_fy,
    ).first()
    if not prev_balance:
        return Decimal("0")

    remaining = Decimal(str(prev_balance.remaining_days))
    if remaining <= 0:
        return Decimal("0")
    if rule.carry_forward_limit and rule.carry_forward_limit > 0:
        return min(remaining, rule.carry_forward_limit)
    return remaining

def get_project_managers_for_employee(employee) -> List:
    """
    Get all unique project managers for projects where the employee is currently allocated.
    
    Returns a list of manager employee objects.
    """
    from apps.allocation.models import Allocation
    from apps.projects.models import Project
    
    # Get current allocations (where end_date is null or in future)
    today = date.today()
    current_allocations = Allocation.objects.filter(
        employee=employee,
        is_deleted=False,
        start_date__lte=today,
    ).filter(
        Q(end_date__isnull=True) | Q(end_date__gte=today)
    ).select_related('project', 'project__manager')
    
    # Extract unique managers
    managers_set = set()
    managers_list = []
    
    for allocation in current_allocations:
        project = allocation.project
        if project.manager and project.manager.id not in managers_set:
            managers_set.add(project.manager.id)
            managers_list.append(project.manager)
    
    return managers_list


def should_notify_managers_for_leave(leave_request) -> bool:
    """
    Determine if managers should be notified for a leave request.
    Currently notifies for all pending leave requests.
    """
    from .models import LeaveRequestStatus
    
    return leave_request.status == LeaveRequestStatus.PENDING