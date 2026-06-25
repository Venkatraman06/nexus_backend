from decimal import Decimal

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
