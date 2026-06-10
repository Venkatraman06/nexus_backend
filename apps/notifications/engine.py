"""Central notification engine — resolves templates, recipients, and delivery."""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Employee
from apps.notifications.constants import ACTIVE_CHANNELS, NotificationChannel
from apps.notifications.events import DomainEvent
from apps.notifications.models import Notification, NotificationEventLog, NotificationTemplate
from apps.notifications.recipients import (
    exclude_actor,
    finance_employees,
    hr_employees,
    managers_and_pmo,
    timesheet_reviewers,
    unique_employees,
)
from apps.notifications.templates_registry import sync_templates

logger = logging.getLogger(__name__)


class NotificationEngine:
    """Processes domain events and creates notification records."""

    @staticmethod
    def _get_template(event_type: str) -> NotificationTemplate | None:
        tpl = NotificationTemplate.objects.filter(event_type=event_type, is_deleted=False).first()
        if not tpl:
            sync_templates()
            tpl = NotificationTemplate.objects.filter(event_type=event_type, is_deleted=False).first()
        return tpl

    @staticmethod
    def _render(template_str: str, context: dict[str, Any]) -> str:
        try:
            return template_str.format(**context)
        except KeyError as exc:
            logger.warning("Template render missing key %s", exc)
            return template_str

    @staticmethod
    def _resolve_action_url(tpl: NotificationTemplate | None, event: DomainEvent) -> str:
        if event.action_url:
            return event.action_url
        if tpl and tpl.default_action_url:
            ctx = {**event.payload, "reference_id": event.reference_id}
            return NotificationEngine._render(tpl.default_action_url, ctx)
        return ""

    @staticmethod
    def resolve_recipients(event: DomainEvent) -> list[Employee]:
        if event.recipient_ids is not None:
            return list(
                Employee.objects.filter(
                    id__in=event.recipient_ids,
                    is_active=True,
                    is_deleted=False,
                )
            )

        payload = event.payload
        et = event.event_type

        if et == "ticket.assigned":
            aid = payload.get("assignee_id")
            return list(Employee.objects.filter(id=aid, is_active=True, is_deleted=False)) if aid else []

        if et == "ticket.due_today":
            aid = payload.get("assignee_id")
            return list(Employee.objects.filter(id=aid, is_active=True, is_deleted=False)) if aid else []

        if et == "project.allocation":
            from apps.projects.models import Project
            recipients = []
            eid = payload.get("employee_id")
            if eid:
                recipients.extend(Employee.objects.filter(id=eid, is_active=True, is_deleted=False))
            pid = payload.get("project_id")
            if pid:
                try:
                    project = Project.objects.select_related("manager").get(pk=pid)
                    if project.manager and project.manager.is_active and not project.manager.is_deleted:
                        recipients.append(project.manager)
                except Project.DoesNotExist:
                    pass
            return exclude_actor(unique_employees(recipients), event.actor_id)

        if et == "project.manager_assigned":
            mid = payload.get("manager_id")
            return list(Employee.objects.filter(id=mid, is_active=True, is_deleted=False)) if mid else []

        if et == "project.due_reminder":
            mid = payload.get("manager_id")
            return list(Employee.objects.filter(id=mid, is_active=True, is_deleted=False)) if mid else []

        if et == "timesheet.submitted":
            from apps.timesheets.models import WeeklyTimesheet
            try:
                weekly = WeeklyTimesheet.objects.select_related("employee__manager").get(
                    pk=event.reference_id
                )
                return exclude_actor(timesheet_reviewers(weekly), event.actor_id)
            except WeeklyTimesheet.DoesNotExist:
                return []

        if et in ("timesheet.approved", "timesheet.rejected"):
            eid = payload.get("employee_id")
            return list(Employee.objects.filter(id=eid, is_active=True, is_deleted=False)) if eid else []

        if et == "employee.onboarded":
            return exclude_actor(
                unique_employees(list(hr_employees()), list(managers_and_pmo())),
                event.actor_id,
            )

        if et == "leave.requested":
            emp_id = payload.get("employee_id")
            groups = [list(hr_employees())]
            if emp_id:
                try:
                    emp = Employee.objects.select_related("manager").get(pk=emp_id)
                    if emp.manager:
                        groups.append([emp.manager])
                except Employee.DoesNotExist:
                    pass
            return exclude_actor(unique_employees(*groups), event.actor_id)

        if et == "payroll.finalized":
            eid = payload.get("employee_id")
            return list(Employee.objects.filter(id=eid, is_active=True, is_deleted=False)) if eid else []

        if et in ("invoice.due_reminder", "milestone.due_reminder", "payment.overdue"):
            return list(finance_employees())

        if et in ("followup.due_today", "followup.overdue"):
            aid = payload.get("assignee_id")
            return list(Employee.objects.filter(id=aid, is_active=True, is_deleted=False)) if aid else []

        if et == "social_post.published":
            # Notify all active employees when a company-wide post is published
            return list(_active_employees())

        if et == "social_post.pending_approval":
            # Recipients already specified in event.recipient_ids
            return []

        return []

    @classmethod
    @transaction.atomic
    def process(cls, event: DomainEvent) -> int:
        actor = None
        if event.actor_id:
            actor = Employee.objects.filter(pk=event.actor_id).first()

        log = NotificationEventLog.objects.create(
            event_type=event.event_type,
            reference_type=event.reference_type,
            reference_id=event.reference_id,
            payload=event.payload,
            actor=actor,
        )

        tpl = cls._get_template(event.event_type)
        recipients = cls.resolve_recipients(event)
        if not recipients:
            log.processed_at = timezone.now()
            log.save(update_fields=["processed_at"])
            return 0

        ctx = {**event.payload, "reference_id": event.reference_id}
        title = cls._render(tpl.title_template, ctx) if tpl else event.event_type
        message = cls._render(tpl.message_template, ctx) if tpl else str(event.payload)
        severity = tpl.severity if tpl else "info"
        action_url = cls._resolve_action_url(tpl, event)

        created = 0
        for recipient in recipients:
            for channel in ACTIVE_CHANNELS:
                dedup_key = event.dedup_key or ""
                if dedup_key and Notification.objects.filter(
                    recipient=recipient, dedup_key=dedup_key
                ).exists():
                    continue

                notif = Notification.objects.create(
                    recipient=recipient,
                    event_type=event.event_type,
                    title=title,
                    message=message,
                    reference_type=event.reference_type,
                    reference_id=event.reference_id,
                    action_url=action_url,
                    severity=severity,
                    channel=channel,
                    dedup_key=dedup_key,
                    metadata=event.payload,
                    actor=actor,
                )
                created += 1

                from apps.notifications.realtime import broadcast_notification
                broadcast_notification(str(recipient.id), {
                    "id": str(notif.id),
                    "title": notif.title,
                    "event_type": notif.event_type,
                })

                if channel != NotificationChannel.IN_APP:
                    cls._dispatch_external(channel, recipient, title, message, action_url)

        log.notifications_created = created
        log.processed_at = timezone.now()
        log.save(update_fields=["notifications_created", "processed_at"])
        return created

    @staticmethod
    def _dispatch_external(channel: str, recipient, title: str, message: str, action_url: str):
        """Stub for future Email / Push / Slack / Teams / WhatsApp delivery."""
        logger.debug(
            "External channel %s not yet implemented for %s: %s",
            channel, recipient.email, title,
        )
