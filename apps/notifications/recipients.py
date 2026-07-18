"""Recipient resolution helpers — decoupled from domain modules."""

from django.db.models import Q

from apps.accounts.models import Employee


def _active_employees():
    return Employee.objects.filter(is_active=True, is_deleted=False)


def hr_employees():
    return _active_employees().filter(keycloak_group__iexact="hr")


def finance_employees():
    return _active_employees().filter(
        Q(keycloak_group__iexact="finance team") | Q(is_pmo=True)
    )


def managers_and_pmo():
    return _active_employees().filter(Q(is_manager=True) | Q(is_pmo=True))


def timesheet_reviewers(weekly) -> list[Employee]:
    """Project managers + reporting manager who can review this timesheet."""
    from apps.workitems.models import WorkLog

    reviewers: dict[str, Employee] = {}

    employee_logs = WorkLog.objects.filter(
        weekly_timesheet=weekly, is_deleted=False,
    ).select_related("ticket__project__manager")

    for wl in employee_logs:
        if wl.ticket and wl.ticket.project and wl.ticket.project.manager_id:
            mgr = wl.ticket.project.manager
            if mgr and mgr.is_active and not mgr.is_deleted:
                reviewers[str(mgr.id)] = mgr

    if weekly.employee.manager_id:
        mgr = weekly.employee.manager
        if mgr and mgr.is_active and not mgr.is_deleted:
            reviewers[str(mgr.id)] = mgr

    return list(reviewers.values())


def exclude_actor(recipients: list[Employee], actor_id: str | None) -> list[Employee]:
    if not actor_id:
        return recipients
    return [r for r in recipients if str(r.id) != str(actor_id)]


def unique_employees(*groups: list[Employee]) -> list[Employee]:
    seen: dict[str, Employee] = {}
    for group in groups:
        for emp in group:
            seen[str(emp.id)] = emp
    return list(seen.values())
