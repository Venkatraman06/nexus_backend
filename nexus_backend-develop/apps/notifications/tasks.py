"""Celery tasks — async delivery and scheduled due-date scans."""

from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="notifications.process_domain_event")
def process_domain_event_task(event_data: dict) -> int:
    from apps.notifications.engine import NotificationEngine
    from apps.notifications.events import DomainEvent

    return NotificationEngine.process(DomainEvent(**event_data))


@shared_task(name="notifications.scan_due_date_reminders")
def scan_due_date_reminders() -> dict:
    """
    Daily scan for ticket due today, project end dates, invoice/milestone due,
    and overdue payments. Idempotent via dedup_key.
    """
    from apps.notifications.constants import EventType, ReferenceType
    from apps.notifications.publisher import publish_event

    today = date.today()
    tomorrow = today + timedelta(days=1)
    counts = {
        "tickets": 0, "projects": 0, "invoices": 0, "milestones": 0, "payments": 0,
        "followups_today": 0, "followups_overdue": 0,
    }

    # ── Tickets due today ─────────────────────────────────────────────
    from apps.tickets.models import Ticket

    for ticket in Ticket.objects.filter(
        due_date=today, is_deleted=False, assignee__isnull=False,
    ).select_related("assignee", "project"):
        publish_event(
            EventType.TICKET_DUE_TODAY,
            ReferenceType.TICKET,
            str(ticket.id),
            payload={
                "ticket_id": ticket.ticket_id,
                "title": ticket.title,
                "due_date": today.isoformat(),
                "assignee_id": str(ticket.assignee_id),
                "project_name": ticket.project.name if ticket.project else "",
            },
            dedup_key=f"ticket.due:{ticket.id}:{today.isoformat()}",
        )
        counts["tickets"] += 1

    # ── Projects ending today ─────────────────────────────────────────
    from apps.projects.models import Project

    for project in Project.objects.filter(
        end_date=today, is_deleted=False, manager__isnull=False,
    ).select_related("manager"):
        publish_event(
            EventType.PROJECT_DUE_REMINDER,
            ReferenceType.PROJECT,
            str(project.id),
            payload={
                "project_name": project.name,
                "end_date": today.isoformat(),
                "manager_id": str(project.manager_id),
            },
            dedup_key=f"project.due:{project.id}:{today.isoformat()}",
        )
        counts["projects"] += 1

    # ── Invoices due tomorrow ─────────────────────────────────────────
    from apps.payment.models import Invoice

    for inv in Invoice.objects.filter(
        due_date=tomorrow, is_deleted=False,
    ).select_related("client", "project"):
        publish_event(
            EventType.INVOICE_DUE_REMINDER,
            ReferenceType.INVOICE,
            str(inv.id),
            payload={
                "invoice_number": inv.invoice_number,
                "client_name": inv.client.name if inv.client else "",
                "amount": str(inv.total_amount),
                "due_date": tomorrow.isoformat(),
            },
            dedup_key=f"invoice.due:{inv.id}:{tomorrow.isoformat()}",
        )
        counts["invoices"] += 1

    # ── Milestones due tomorrow ───────────────────────────────────────
    from apps.payment.models import Milestone

    for ms in Milestone.objects.filter(
        due_date=tomorrow, is_deleted=False,
    ).select_related("project"):
        publish_event(
            EventType.MILESTONE_DUE_REMINDER,
            ReferenceType.MILESTONE,
            str(ms.id),
            payload={
                "milestone_name": ms.milestone_name,
                "project_name": ms.project.name if ms.project else "",
                "due_date": tomorrow.isoformat(),
            },
            dedup_key=f"milestone.due:{ms.id}:{tomorrow.isoformat()}",
        )
        counts["milestones"] += 1

    # ── Overdue invoices ──────────────────────────────────────────────
    for inv in Invoice.objects.filter(
        due_date__lt=today, is_deleted=False, is_cancelled=False,
    ).select_related("client"):
        if inv.pending_amount <= 0:
            continue
        days = inv.days_overdue
        publish_event(
            EventType.PAYMENT_OVERDUE,
            ReferenceType.INVOICE,
            str(inv.id),
            payload={
                "invoice_number": inv.invoice_number,
                "days_overdue": days,
                "outstanding": str(inv.pending_amount),
            },
            dedup_key=f"payment.overdue:{inv.id}:{today.isoformat()}",
        )
        counts["payments"] += 1

    # ── Follow-ups (planning/inprogress, assignee only) ───────────────
    from apps.followups.notifications import scan_followup_reminders

    followup_counts = scan_followup_reminders(today=today)
    counts["followups_today"] = followup_counts["followups_today"]
    counts["followups_overdue"] = followup_counts["followups_overdue"]

    logger.info("Due-date scan complete: %s", counts)
    return counts
