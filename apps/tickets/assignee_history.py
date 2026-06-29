"""Record and query ticket assignee time windows."""

from __future__ import annotations

from django.utils import timezone


def record_initial_assignee(ticket, *, changed_by=None):
    from .models import TicketAssigneeHistory

    if not ticket.assignee_id:
        return
    if TicketAssigneeHistory.objects.filter(ticket=ticket).exists():
        return
    TicketAssigneeHistory.objects.create(
        ticket=ticket,
        employee_id=ticket.assignee_id,
        effective_from=ticket.created_at or timezone.now(),
        changed_by=changed_by,
    )


def record_assignee_change(ticket, old_assignee_id, new_assignee_id, *, changed_by=None):
    from .models import TicketAssigneeHistory

    if old_assignee_id == new_assignee_id:
        return

    now = timezone.now()
    TicketAssigneeHistory.objects.filter(
        ticket=ticket,
        effective_to__isnull=True,
    ).update(effective_to=now)

    if new_assignee_id:
        TicketAssigneeHistory.objects.create(
            ticket=ticket,
            employee_id=new_assignee_id,
            effective_from=now,
            changed_by=changed_by,
        )
