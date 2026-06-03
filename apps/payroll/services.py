"""
Payroll auto-generation service.

Given an employee, month, year:
1. Look up the RateCard for their designation × department.
2. Count working days, present days, leave days from AttendanceRecord.
3. Compute payable salary = hr_daily_rate × payable_days.
4. Split into: Basic (40%), HRA (20%), Allowances (40%).
5. Compute deductions: PF (12% of Basic), TDS (simplified slab).
6. Create / update a Payroll record.
"""

import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from apps.attendance.models import AttendanceRecord, AttendanceStatus


def _working_days_in_month(year: int, month: int) -> int:
    """Count Mon-Fri days in the given month."""
    _, days_in_month = calendar.monthrange(year, month)
    return sum(
        1 for d in range(1, days_in_month + 1)
        if date(year, month, d).weekday() < 5
    )


def _tds(annual_gross: Decimal) -> Decimal:
    """Simplified TDS slab (FY 2024-25 new regime)."""
    if annual_gross <= Decimal("300000"):
        return Decimal("0")
    elif annual_gross <= Decimal("600000"):
        return (annual_gross - Decimal("300000")) * Decimal("0.05") / 12
    elif annual_gross <= Decimal("900000"):
        return (
            Decimal("300000") * Decimal("0.05")
            + (annual_gross - Decimal("600000")) * Decimal("0.10")
        ) / 12
    elif annual_gross <= Decimal("1200000"):
        return (
            Decimal("300000") * Decimal("0.05")
            + Decimal("300000") * Decimal("0.10")
            + (annual_gross - Decimal("900000")) * Decimal("0.15")
        ) / 12
    else:
        return (
            Decimal("300000") * Decimal("0.05")
            + Decimal("300000") * Decimal("0.10")
            + Decimal("300000") * Decimal("0.15")
            + (annual_gross - Decimal("1200000")) * Decimal("0.20")
        ) / 12


def generate_payroll(employee, month: int, year: int, created_by=None):
    """
    Auto-generate (or regenerate) a payroll entry.
    Returns (payroll_instance, was_created: bool, error_message: str | None).
    """
    from apps.master.models import RateCard
    from .models import Payroll, PayrollStatus

    # ── Rate card lookup ──────────────────────────────────────────────────────
    desig_id = employee.designation_ref_id
    dept_id  = employee.department_ref_id

    rate_card = RateCard.objects.filter(
        designation_ref_id=desig_id,
        department_ref_id=dept_id,
        is_active=True,
    ).first()

    if not rate_card:
        return None, False, (
            f"No active rate card found for "
            f"{getattr(employee.designation_ref, 'name', '?')} / "
            f"{getattr(employee.department_ref, 'name', '?')}."
        )

    # ── Attendance counts ─────────────────────────────────────────────────────
    total_working = _working_days_in_month(year, month)
    att_qs = AttendanceRecord.objects.filter(
        employee=employee,
        date__year=year,
        date__month=month,
        is_deleted=False,
    )
    present_days = att_qs.filter(
        status__in=[AttendanceStatus.PRESENT, AttendanceStatus.WFH]
    ).count()
    half_days = att_qs.filter(status=AttendanceStatus.HALF_DAY).count()
    leave_days = att_qs.filter(status=AttendanceStatus.ON_LEAVE).count()

    # Payable days = full present + half days counted as 0.5
    payable_days = Decimal(present_days) + Decimal(half_days) * Decimal("0.5")

    # ── Salary calculation ────────────────────────────────────────────────────
    daily_rate   = rate_card.hr_daily_rate
    monthly_ctc  = (daily_rate * payable_days).quantize(Decimal("0.01"), ROUND_HALF_UP)

    basic        = (monthly_ctc * Decimal("0.40")).quantize(Decimal("0.01"), ROUND_HALF_UP)
    hra          = (monthly_ctc * Decimal("0.20")).quantize(Decimal("0.01"), ROUND_HALF_UP)
    allowances   = (monthly_ctc - basic - hra).quantize(Decimal("0.01"), ROUND_HALF_UP)

    pf           = (basic * Decimal("0.12")).quantize(Decimal("0.01"), ROUND_HALF_UP)
    annual_gross = monthly_ctc * 12
    tds          = _tds(annual_gross).quantize(Decimal("0.01"), ROUND_HALF_UP)

    # ── Create or update payroll ──────────────────────────────────────────────
    defaults = {
        "basic_salary":   basic,
        "hra":            hra,
        "allowances":     allowances,
        "overtime":       Decimal("0"),
        "pf":             pf,
        "tds":            tds,
        "other_deductions": Decimal("0"),
        "advance_deduction": Decimal("0"),
        "working_days":   total_working,
        "present_days":   present_days,
        "leave_days":     leave_days,
        "status":         PayrollStatus.DRAFT,
    }
    if created_by:
        defaults["created_by"] = created_by

    payroll, created = Payroll.objects.update_or_create(
        employee=employee,
        month=month,
        year=year,
        defaults=defaults,
    )
    return payroll, created, None
