"""
Timesheet business logic — validation, weekly generation, copy, approval.
"""
from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from django.db.models import Q, Sum
from django.utils import timezone
from rest_framework import serializers

from apps.allocation.models import Allocation
from apps.attendance.models import AttendanceRecord, AttendanceStatus
from apps.tickets.models import Ticket, TicketType
from apps.workitems.models import WorkLog

from apps.common.constants import TimesheetStatus

from .models import TimesheetConfig, TimesheetReviewLog, WeeklyTimesheet

LOGGABLE_TICKET_TYPES = {
    TicketType.TASK,
    TicketType.BUG,
    TicketType.CHANGE_REQUEST,
    TicketType.SUBTASK,
}

CLOSED_STATE_SLUGS = ("done", "closed", "cancelled", "canceled")

# Sun–Sat calendar week; expected hours still based on Mon–Fri working days
CALENDAR_WEEK_DAYS = 7
WORKING_DAYS_PER_WEEK = 5

LOGGABLE_ATTENDANCE_STATUSES = {
    AttendanceStatus.PRESENT,
    AttendanceStatus.WFH,
    AttendanceStatus.HALF_DAY,
}


def week_bounds(anchor: date | None = None) -> tuple[date, date]:
    """Return (Sunday, Saturday) for the calendar week containing anchor (default today)."""
    anchor = anchor or date.today()
    days_since_sunday = (anchor.weekday() + 1) % 7
    sunday = anchor - timedelta(days=days_since_sunday)
    saturday = sunday + timedelta(days=CALENDAR_WEEK_DAYS - 1)
    return sunday, saturday


def is_working_day(d: date) -> bool:
    return d.weekday() < WORKING_DAYS_PER_WEEK


def is_current_week(anchor: date | None = None) -> bool:
    """True when anchor falls in the same Sun–Sat week as today."""
    anchor = anchor or date.today()
    current_sunday, _ = week_bounds(date.today())
    view_sunday, _ = week_bounds(anchor)
    return view_sunday == current_sunday


def assert_current_week_only(log_date: date) -> None:
    """Raise if time logging is attempted outside the current week."""
    if not is_current_week(log_date):
        raise serializers.ValidationError(
            "Time can only be logged for the current week."
        )


def get_daily_capacity() -> Decimal:
    return Decimal(str(TimesheetConfig.get_daily_capacity()))


def get_active_allocations(employee, log_date: date):
    return Allocation.objects.filter(
        employee=employee,
        is_deleted=False,
        start_date__lte=log_date,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=log_date))


def validate_employment_window(employee, log_date: date) -> str | None:
    """Return error message if log_date is outside joining/retirement dates."""
    joining = getattr(employee, "joining_date", None)
    retirement = getattr(employee, "retirement_date", None)
    if joining and log_date < joining:
        return f"Cannot log time before joining date ({joining:%d %b %Y})."
    if retirement and log_date > retirement:
        return f"Cannot log time after retirement date ({retirement:%d %b %Y})."
    return None


def validate_attendance_for_log(employee, log_date: date) -> str | None:
    """Time may only be logged when attendance check-in and check-out exist for the date."""
    emp_err = validate_employment_window(employee, log_date)
    if emp_err:
        return emp_err

    record = AttendanceRecord.objects.filter(
        employee=employee,
        date=log_date,
        is_deleted=False,
    ).first()

    if not record:
        return (
            f"No attendance for {log_date:%d %b %Y}. "
            "Mark check-in and check-out before logging time."
        )

    if record.status not in LOGGABLE_ATTENDANCE_STATUSES:
        return (
            f"Attendance on {log_date:%d %b %Y} is {record.get_status_display()}. "
            "Time cannot be logged on this date."
        )

    if not record.check_in:
        return f"Check-in not recorded for {log_date:%d %b %Y}."

    if not record.check_out:
        return (
            f"Check-out not recorded for {log_date:%d %b %Y}. "
            "Complete attendance (start to end) before logging time."
        )

    return None


def get_loggable_dates(employee, start: date, end: date) -> list[date]:
    """Dates in range where the employee may log time (attendance start + end marked)."""
    qs = AttendanceRecord.objects.filter(
        employee=employee,
        date__range=[start, end],
        is_deleted=False,
        status__in=LOGGABLE_ATTENDANCE_STATUSES,
        check_in__isnull=False,
        check_out__isnull=False,
    ).values_list("date", flat=True)

    dates = list(qs)
    joining = getattr(employee, "joining_date", None)
    retirement = getattr(employee, "retirement_date", None)
    if joining:
        dates = [d for d in dates if d >= joining]
    if retirement:
        dates = [d for d in dates if d <= retirement]
    return sorted(dates)


def get_allocated_project_ids(employee, log_date: date) -> set:
    return set(
        get_active_allocations(employee, log_date).values_list("project_id", flat=True)
    )


def project_capacity_for_date(employee, project_id, log_date: date) -> Decimal:
    """Daily hours allowed on a project based on allocation %."""
    daily = get_daily_capacity()
    pct = get_active_allocations(employee, log_date).filter(
        project_id=project_id
    ).aggregate(t=Sum("allocation_percentage"))["t"] or 0
    return (Decimal(str(pct)) / Decimal("100")) * daily


def is_ticket_active(ticket: Ticket) -> bool:
    if ticket.is_deleted or not ticket.is_active:
        return False
    slug = (getattr(ticket.workflow_state, "slug", None) or "").lower()
    return not any(term in slug for term in CLOSED_STATE_SLUGS)


def get_loggable_tickets(employee, log_date: date, search: str = ""):
    """Tickets an employee may log time against."""
    tickets, _ = get_loggable_tickets_with_hints(employee, log_date, search)
    return tickets


def get_loggable_tickets_with_hints(employee, log_date: date, search: str = ""):
    """
    Return (tickets, hints) for the log-time dropdown.
    Requires: active allocation on log_date + assigned Task/Bug/CR on that project.
    """
    hints: list[str] = []
    att_err = validate_attendance_for_log(employee, log_date)
    if att_err:
        hints.append(att_err)
        return [], hints

    allocated_ids = get_allocated_project_ids(employee, log_date)

    if not allocated_ids:
        hints.append(
            f"No active project allocation on {log_date:%d %b %Y}. "
            "Pick a date within your allocation period."
        )
        return [], hints

    assigned_any = Ticket.objects.filter(
        assignee=employee,
        is_deleted=False,
        type__in=LOGGABLE_TICKET_TYPES,
    )
    if not assigned_any.exists():
        hints.append("No Task, Bug, or CR tickets are assigned to you.")

    assigned_on_alloc = assigned_any.filter(project_id__in=allocated_ids)
    if assigned_any.exists() and not assigned_on_alloc.exists():
        hints.append(
            "Your assigned tickets are on projects you are not allocated to on this date."
        )

    qs = assigned_on_alloc.filter(
        is_deleted=False,
        is_active=True,
    ).select_related("project", "parent", "workflow_state")

    if search:
        qs = qs.filter(
            Q(ticket_id__icontains=search)
            | Q(title__icontains=search)
            | Q(project__name__icontains=search)
        )

    active = [t for t in qs if is_ticket_active(t)]
    inactive_count = qs.count() - len(active)
    if inactive_count > 0:
        hints.append(f"{inactive_count} assigned ticket(s) are closed and cannot be logged against.")

    if not active and not hints:
        hints.append("No loggable tickets match your search.")

    return active, hints


def validate_work_log(*, employee, ticket: Ticket, log_date: date, hours: Decimal,
                      work_log_id=None) -> dict:
    """
    Validate a work log entry. Returns warnings dict; raises ValidationError on hard failures.
    """
    warnings: dict = {}

    att_err = validate_attendance_for_log(employee, log_date)
    if att_err:
        raise serializers.ValidationError({"log_date": att_err})

    if ticket.type not in LOGGABLE_TICKET_TYPES:
        raise serializers.ValidationError(
            {"ticket": "Time can only be logged against Task, Bug, or Change Request tickets."}
        )

    if not is_ticket_active(ticket):
        raise serializers.ValidationError({"ticket": "Cannot log time on a closed ticket."})

    allocated_ids = get_allocated_project_ids(employee, log_date)
    if ticket.project_id not in allocated_ids:
        raise serializers.ValidationError(
            {"log_date": "You are not allocated to this project on the selected date."}
        )

    if ticket.assignee_id != employee.id:
        raise serializers.ValidationError(
            {"ticket": "You can only log time on tickets assigned to you."}
        )

    if hours <= 0:
        raise serializers.ValidationError({"hours": "Hours must be greater than zero."})

    daily_cap = get_daily_capacity()
    existing = WorkLog.objects.filter(
        employee=employee, log_date=log_date, is_deleted=False,
    )
    if work_log_id:
        existing = existing.exclude(pk=work_log_id)
    day_total = Decimal(str(existing.aggregate(t=Sum("hours"))["t"] or 0)) + hours
    if day_total > daily_cap:
        warnings["daily_capacity"] = (
            f"Logged {day_total}h exceeds daily capacity of {daily_cap}h."
        )

    proj_cap = project_capacity_for_date(employee, ticket.project_id, log_date)
    proj_existing = existing.filter(ticket__project_id=ticket.project_id)
    proj_total = Decimal(str(proj_existing.aggregate(t=Sum("hours"))["t"] or 0)) + hours
    if proj_cap > 0 and proj_total > proj_cap:
        warnings["project_capacity"] = (
            f"Logged {proj_total}h on this project exceeds allocated capacity of {proj_cap}h."
        )

    return warnings


def get_or_create_weekly_timesheet(employee, anchor: date | None = None) -> WeeklyTimesheet:
    sunday, saturday = week_bounds(anchor)
    daily = get_daily_capacity()
    expected = daily * WORKING_DAYS_PER_WEEK

    ts = WeeklyTimesheet.objects.filter(
        employee=employee,
        week_start=sunday,
        is_deleted=False,
    ).first()

    if not ts:
        legacy_monday = sunday + timedelta(days=1)
        ts = WeeklyTimesheet.objects.filter(
            employee=employee,
            week_start=legacy_monday,
            is_deleted=False,
        ).first()
        if ts:
            ts.week_start = sunday
            ts.week_end = saturday
            ts.expected_hours = expected
            ts.save(update_fields=["week_start", "week_end", "expected_hours"])

    if not ts:
        deleted = WeeklyTimesheet.objects.filter(
            employee=employee,
            week_start=sunday,
            is_deleted=True,
        ).first()
        if not deleted:
            deleted = WeeklyTimesheet.objects.filter(
                employee=employee,
                week_start=sunday + timedelta(days=1),
                is_deleted=True,
            ).first()
        if deleted:
            deleted.restore()
            ts = deleted
            ts.week_start = sunday
            ts.week_end = saturday
            ts.expected_hours = expected
            ts.save(update_fields=["week_start", "week_end", "expected_hours"])
        else:
            ts = WeeklyTimesheet.objects.create(
                employee=employee,
                week_start=sunday,
                week_end=saturday,
                expected_hours=expected,
                status=TimesheetStatus.DRAFT,
            )

    if ts.week_start != sunday:
        ts.week_start = sunday
    if ts.week_end != saturday:
        ts.week_end = saturday
    if ts.week_start != sunday or ts.week_end != saturday:
        ts.expected_hours = expected
        ts.save(update_fields=["week_start", "week_end", "expected_hours"])
    elif ts.expected_hours != expected:
        ts.expected_hours = expected
        ts.save(update_fields=["expected_hours"])
    refresh_weekly_totals(ts)
    return ts


def refresh_weekly_totals(weekly: WeeklyTimesheet) -> None:
    total = WorkLog.objects.filter(
        weekly_timesheet=weekly,
        is_deleted=False,
    ).aggregate(t=Sum("hours"))["t"] or 0
    weekly.total_hours = total
    weekly.save(update_fields=["total_hours", "updated_at"])


def link_work_log_to_week(work_log: WorkLog) -> None:
    weekly = get_or_create_weekly_timesheet(work_log.employee, work_log.log_date)
    if weekly.status in (TimesheetStatus.APPROVED, TimesheetStatus.SUBMITTED):
        if work_log.pk:
            raise serializers.ValidationError(
                "Cannot modify logs on a submitted or approved timesheet."
            )
    work_log.weekly_timesheet = weekly
    work_log.save(update_fields=["weekly_timesheet"])
    refresh_weekly_totals(weekly)


def assert_week_editable(weekly: WeeklyTimesheet) -> None:
    if weekly.status in (TimesheetStatus.SUBMITTED, TimesheetStatus.APPROVED):
        raise serializers.ValidationError(
            f"Timesheet is {weekly.status.lower()} and cannot be edited."
        )


def submit_timesheet(weekly: WeeklyTimesheet, employee) -> WeeklyTimesheet:
    if weekly.employee_id != employee.id:
        raise serializers.ValidationError("You can only submit your own timesheet.")
    if not is_current_week(weekly.week_start):
        raise serializers.ValidationError("You can only submit the current week's timesheet.")
    if weekly.status != TimesheetStatus.DRAFT and weekly.status != TimesheetStatus.REJECTED:
        raise serializers.ValidationError(f"Cannot submit a {weekly.status.lower()} timesheet.")

    weekly.status = TimesheetStatus.SUBMITTED
    weekly.submitted_at = timezone.now()
    weekly.review_comment = ""
    weekly.save(update_fields=["status", "submitted_at", "review_comment", "updated_at"])

    TimesheetReviewLog.objects.create(
        weekly_timesheet=weekly,
        action="SUBMIT",
        performed_by=employee,
        created_by=employee,
    )

    from apps.notifications.constants import EventType, ReferenceType
    from apps.notifications.publisher import publish_event
    publish_event(
        EventType.TIMESHEET_SUBMITTED,
        ReferenceType.TIMESHEET,
        str(weekly.id),
        payload={
            "employee_name": employee.full_name,
            "employee_id": str(employee.id),
            "week_start": weekly.week_start.isoformat(),
            "week_end": weekly.week_end.isoformat(),
            "total_hours": str(weekly.total_hours),
        },
        actor_id=str(employee.id),
        async_delivery=True,
    )

    return weekly


def approve_timesheet(weekly: WeeklyTimesheet, reviewer, comment: str = "",
                      user_permissions: list | None = None) -> WeeklyTimesheet:
    if weekly.employee_id == reviewer.id:
        raise serializers.ValidationError("You cannot approve your own timesheet.")
    if weekly.status != TimesheetStatus.SUBMITTED:
        raise serializers.ValidationError("Only submitted timesheets can be approved.")
    if not can_review_timesheet(reviewer, weekly, user_permissions):
        raise serializers.ValidationError("You are not authorized to approve this timesheet.")

    weekly.status = TimesheetStatus.APPROVED
    weekly.reviewed_at = timezone.now()
    weekly.reviewed_by = reviewer
    weekly.review_comment = comment
    weekly.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_comment", "updated_at"])

    TimesheetReviewLog.objects.create(
        weekly_timesheet=weekly,
        action="APPROVE",
        comment=comment,
        performed_by=reviewer,
        created_by=reviewer,
    )

    from apps.notifications.constants import EventType, ReferenceType
    from apps.notifications.publisher import publish_event
    publish_event(
        EventType.TIMESHEET_APPROVED,
        ReferenceType.TIMESHEET,
        str(weekly.id),
        payload={
            "employee_id": str(weekly.employee_id),
            "week_start": weekly.week_start.isoformat(),
            "week_end": weekly.week_end.isoformat(),
        },
        actor_id=str(reviewer.id),
        async_delivery=True,
    )

    return weekly


def reject_timesheet(weekly: WeeklyTimesheet, reviewer, comment: str = "",
                     user_permissions: list | None = None) -> WeeklyTimesheet:
    if weekly.employee_id == reviewer.id:
        raise serializers.ValidationError("You cannot reject your own timesheet.")
    if weekly.status != TimesheetStatus.SUBMITTED:
        raise serializers.ValidationError("Only submitted timesheets can be rejected.")
    if not can_review_timesheet(reviewer, weekly, user_permissions):
        raise serializers.ValidationError("You are not authorized to reject this timesheet.")

    weekly.status = TimesheetStatus.REJECTED
    weekly.reviewed_at = timezone.now()
    weekly.reviewed_by = reviewer
    weekly.review_comment = comment
    weekly.save(update_fields=["status", "reviewed_at", "reviewed_by", "review_comment", "updated_at"])

    TimesheetReviewLog.objects.create(
        weekly_timesheet=weekly,
        action="REJECT",
        comment=comment,
        performed_by=reviewer,
        created_by=reviewer,
    )

    from apps.notifications.constants import EventType, ReferenceType
    from apps.notifications.publisher import publish_event
    publish_event(
        EventType.TIMESHEET_REJECTED,
        ReferenceType.TIMESHEET,
        str(weekly.id),
        payload={
            "employee_id": str(weekly.employee_id),
            "week_start": weekly.week_start.isoformat(),
            "week_end": weekly.week_end.isoformat(),
            "comment": comment or "Please review and resubmit.",
        },
        actor_id=str(reviewer.id),
        async_delivery=True,
    )

    return weekly


def managed_project_ids(manager) -> set:
    from apps.projects.models import Project
    return set(
        Project.objects.filter(manager=manager, is_deleted=False).values_list("id", flat=True)
    )


def can_review_timesheet(reviewer, weekly: WeeklyTimesheet, user_permissions: list | None = None) -> bool:
    if reviewer.is_staff or getattr(reviewer, "is_superuser", False):
        return True
    perms = user_permissions or []
    if "pmt.project.timesheet.approve" in perms:
        return True

    managed = managed_project_ids(reviewer)
    employee_logs = WorkLog.objects.filter(
        weekly_timesheet=weekly, is_deleted=False,
    ).select_related("ticket__project")
    log_projects = {wl.ticket.project_id for wl in employee_logs if wl.ticket}

    if log_projects & managed:
        return True

    # Reporting manager
    if weekly.employee.manager_id == reviewer.id:
        return True

    return False


def copy_logs_from_date(employee, source_date: date, target_date: date) -> list[WorkLog]:
    assert_current_week_only(target_date)
    assert_week_editable(get_or_create_weekly_timesheet(employee, target_date))
    source_logs = WorkLog.objects.filter(
        employee=employee, log_date=source_date, is_deleted=False,
    )
    created = []
    for src in source_logs:
        wl = WorkLog.objects.create(
            employee=employee,
            ticket=src.ticket,
            log_date=target_date,
            hours=src.hours,
            description=src.description,
            remarks=src.remarks,
            category=src.category,
            is_billable=src.is_billable,
            created_by=employee,
        )
        link_work_log_to_week(wl)
        created.append(wl)
    return created


def copy_logs_from_week(employee, source_week_start: date, target_week_start: date) -> int:
    src_sun, _ = week_bounds(source_week_start)
    tgt_sun, _ = week_bounds(target_week_start)
    count = 0
    for offset in range(CALENDAR_WEEK_DAYS):
        src_day = src_sun + timedelta(days=offset)
        tgt_day = tgt_sun + timedelta(days=offset)
        count += len(copy_logs_from_date(employee, src_day, tgt_day))
    return count


def manager_dashboard(manager) -> dict:
    managed = managed_project_ids(manager)
    submitted = WeeklyTimesheet.objects.filter(
        status=TimesheetStatus.SUBMITTED, is_deleted=False,
    )
    if not (manager.is_staff or getattr(manager, "is_superuser", False)):
        submitted_ids = set()
        for ts in submitted.select_related("employee"):
            if can_review_timesheet(manager, ts):
                submitted_ids.add(ts.id)
        submitted = submitted.filter(id__in=submitted_ids)

    sunday, _ = week_bounds()
    approved_week = WeeklyTimesheet.objects.filter(
        status=TimesheetStatus.APPROVED,
        reviewed_at__date__gte=sunday,
        is_deleted=False,
    )
    rejected_week = WeeklyTimesheet.objects.filter(
        status=TimesheetStatus.REJECTED,
        reviewed_at__date__gte=sunday,
        is_deleted=False,
    )

    missing = missing_timesheets(manager)

    return {
        "pending_reviews": submitted.count(),
        "approved_this_week": approved_week.count(),
        "rejected_this_week": rejected_week.count(),
        "missing_timesheets": len(missing),
        "missing_details": missing[:20],
    }


def missing_timesheets(manager=None) -> list[dict]:
    """Employees with active allocation but no submitted timesheet for current week."""
    today = date.today()
    sunday, saturday = week_bounds(today)

    allocations = Allocation.objects.filter(
        is_deleted=False,
        start_date__lte=saturday,
    ).filter(Q(end_date__isnull=True) | Q(end_date__gte=sunday))

    if manager:
        managed = managed_project_ids(manager)
        allocations = allocations.filter(project_id__in=managed)

    employee_ids = allocations.values_list("employee_id", flat=True).distinct()

    from apps.accounts.models import Employee
    missing = []
    for emp in Employee.objects.filter(id__in=employee_ids, is_active=True, is_deleted=False):
        ts = WeeklyTimesheet.objects.filter(
            employee=emp, week_start=sunday, is_deleted=False,
        ).first()
        if not ts:
            ts = WeeklyTimesheet.objects.filter(
                employee=emp,
                week_start=sunday + timedelta(days=1),
                is_deleted=False,
            ).first()
        if not ts or ts.status in (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED):
            missing.append({
                "employee_id": str(emp.id),
                "employee_name": emp.full_name,
                "week_start": str(sunday),
                "status": ts.status if ts else "MISSING",
            })
    return missing


def ticket_hierarchy(ticket: Ticket) -> dict:
    """Resolve epic/story from parent chain."""
    epic_title = ""
    story_title = ""
    current = ticket.parent
    ancestors = []
    while current:
        ancestors.append(current)
        current = current.parent
    for anc in ancestors:
        if anc.type == TicketType.EPIC:
            epic_title = anc.title
        elif anc.type == TicketType.STORY:
            story_title = anc.title
    return {
        "epic_title": epic_title,
        "story_title": story_title,
    }
