"""Follow-up in-app notifications — assignee only, planning/inprogress only."""

from __future__ import annotations

from datetime import date

from apps.notifications.constants import EventType, ReferenceType
from apps.notifications.publisher import publish_event

ACTIVE_STATE_SLUGS = ("planning", "inprogress")


def is_notifiable_followup(followup) -> bool:
    """Only planning/inprogress follow-ups with an assignee and due date."""
    if followup.is_deleted or not followup.assignee_id or not followup.due_date:
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


def publish_followup_due_today(followup, *, today: date | None = None) -> bool:
    if not is_notifiable_followup(followup):
        return False
    today = today or date.today()
    if followup.due_date != today:
        return False

    time_suffix = _time_suffix(followup)
    publish_event(
        EventType.FOLLOWUP_DUE_TODAY,
        ReferenceType.FOLLOWUP,
        str(followup.id),
        payload={
            "title": followup.title,
            "type_label": followup.get_type_display(),
            "priority_label": followup.get_priority_display(),
            "due_date": today.isoformat(),
            "time_window": time_suffix.strip(" ()"),
            "time_suffix": time_suffix,
            "assignee_id": str(followup.assignee_id),
        },
        dedup_key=f"followup.due_today:{followup.id}:{today.isoformat()}",
    )
    return True


def publish_followup_overdue(followup, *, today: date | None = None) -> bool:
    if not is_notifiable_followup(followup):
        return False
    today = today or date.today()
    if followup.due_date >= today:
        return False

    days_overdue = (today - followup.due_date).days
    if days_overdue < 1:
        return False

    publish_event(
        EventType.FOLLOWUP_OVERDUE,
        ReferenceType.FOLLOWUP,
        str(followup.id),
        payload={
            "title": followup.title,
            "type_label": followup.get_type_display(),
            "priority_label": followup.get_priority_display(),
            "due_date": followup.due_date.isoformat(),
            "days_overdue": days_overdue,
            "assignee_id": str(followup.assignee_id),
        },
        dedup_key=f"followup.overdue:{followup.id}:{today.isoformat()}",
    )
    return True


def publish_followup_reminders(followup, *, actor_id: str | None = None) -> None:
    """Notify assignee when a follow-up is saved and qualifies."""
    if not is_notifiable_followup(followup):
        return
    today = date.today()
    if followup.due_date == today:
        publish_followup_due_today(followup, today=today)
    elif followup.due_date < today:
        publish_followup_overdue(followup, today=today)


def scan_followup_reminders(*, today: date | None = None) -> dict[str, int]:
    """Daily scan — due today + any overdue (planning/inprogress, assignee only)."""
    from apps.followups.models import FollowUp
    from apps.followups.workflow import ensure_followup_workflow

    ensure_followup_workflow()
    today = today or date.today()
    counts = {"followups_today": 0, "followups_overdue": 0}

    qs = FollowUp.objects.filter(
        is_deleted=False,
        assignee__isnull=False,
        due_date__isnull=False,
        workflow_state__slug__in=ACTIVE_STATE_SLUGS,
    ).select_related("assignee", "workflow_state")

    for followup in qs.filter(due_date=today):
        if publish_followup_due_today(followup, today=today):
            counts["followups_today"] += 1

    for followup in qs.filter(due_date__lt=today):
        if publish_followup_overdue(followup, today=today):
            counts["followups_overdue"] += 1

    return counts
