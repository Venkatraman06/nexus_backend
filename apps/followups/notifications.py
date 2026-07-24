"""Follow-up in-app notifications — assignee only, planning/inprogress only."""

from __future__ import annotations

from datetime import date

from apps.notifications.constants import EventType, ReferenceType
from apps.notifications.publisher import publish_event

ACTIVE_STATE_SLUGS = ("planning", "inprogress")


def is_notifiable_followup(followup) -> bool:
    """Only planning/inprogress follow-ups with assignees and due date."""
    if followup.is_deleted or not followup.end_date:
        return False
    # Check if followup has any assignees
    if not followup.assignees.exists():
        return False
    slug = getattr(getattr(followup, "workflow_state", None), "slug", None)
    return slug in ACTIVE_STATE_SLUGS


def _time_suffix(followup) -> str:
    if followup.start_time and followup.end_time:
        start = followup.start_time.strftime("%I:%M %p").lstrip("0")
        end = followup.end_time.strftime("%I:%M %p").lstrip("0")
        return f" ({start} – {end})"
    if followup.start_time:
        return f" at {followup.start_time.strftime('%I:%M %p').lstrip('0')}"
    return ""


def publish_followup_due_today(followup, *, today: date | None = None, actor_id: str | None = None) -> bool:
    if not is_notifiable_followup(followup):
        return False
    today = today or date.today()
    if followup.end_date != today:
        return False

    time_suffix = _time_suffix(followup)
    
    # Publish event for each assignee
    assignee_ids = [str(a.id) for a in followup.assignees.all()]
    for assignee_id in assignee_ids:
        publish_event(
            EventType.FOLLOWUP_DUE_TODAY,
            ReferenceType.FOLLOWUP,
            str(followup.id),
            payload={
                "title": followup.title,
                "type_label": followup.get_type_display(),
                "priority_label": followup.get_priority_display(),
                "end_date": today.isoformat(),
                "time_window": time_suffix.strip(" ()"),
                "time_suffix": time_suffix,
                "assignee_id": assignee_id,
            },
            dedup_key=f"followup.due_today:{followup.id}:{assignee_id}:{today.isoformat()}",
            actor_id=actor_id,
        )
    return True


def publish_followup_overdue(followup, *, today: date | None = None, actor_id: str | None = None) -> bool:
    if not is_notifiable_followup(followup):
        return False
    today = today or date.today()
    if followup.end_date >= today:
        return False

    days_overdue = (today - followup.end_date).days
    if days_overdue < 1:
        return False

    # Publish event for each assignee
    assignee_ids = [str(a.id) for a in followup.assignees.all()]
    for assignee_id in assignee_ids:
        publish_event(
            EventType.FOLLOWUP_OVERDUE,
            ReferenceType.FOLLOWUP,
            str(followup.id),
            payload={
                "title": followup.title,
                "type_label": followup.get_type_display(),
                "priority_label": followup.get_priority_display(),
                "end_date": followup.end_date.isoformat(),
                "days_overdue": days_overdue,
                "assignee_id": assignee_id,
            },
            dedup_key=f"followup.overdue:{followup.id}:{assignee_id}:{today.isoformat()}",
            actor_id=actor_id,
        )
    return True


def publish_followup_reminders(followup, *, actor_id: str | None = None) -> None:
    """Notify assignee when a follow-up is saved and qualifies."""
    if not is_notifiable_followup(followup):
        return
    today = date.today()
    if followup.end_date == today:
        publish_followup_due_today(followup, today=today, actor_id=actor_id)
    elif followup.end_date < today:
        publish_followup_overdue(followup, today=today, actor_id=actor_id)


def scan_followup_reminders(*, today: date | None = None) -> dict[str, int]:
    """Daily scan — due today + any overdue (planning/inprogress, assignees only)."""
    from apps.followups.models import FollowUp
    from apps.followups.workflow import ensure_followup_workflow

    ensure_followup_workflow()
    today = today or date.today()
    counts = {"followups_today": 0, "followups_overdue": 0}

    qs = FollowUp.objects.filter(
        is_deleted=False,
        end_date__isnull=False,
        workflow_state__slug__in=ACTIVE_STATE_SLUGS,
    ).prefetch_related("assignees").select_related("workflow_state")

    for followup in qs.filter(end_date=today):
        if followup.assignees.exists() and publish_followup_due_today(followup, today=today):
            counts["followups_today"] += 1

    for followup in qs.filter(end_date__lt=today):
        if followup.assignees.exists() and publish_followup_overdue(followup, today=today):
            counts["followups_overdue"] += 1

    return counts
