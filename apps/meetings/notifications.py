"""Meeting in-app notifications — assignee only, planning/inprogress only."""

from __future__ import annotations

from datetime import date

from apps.notifications.constants import EventType, ReferenceType
from apps.notifications.publisher import publish_event

ACTIVE_STATE_SLUGS = ("planning", "inprogress")


def is_notifiable_meeting(meeting) -> bool:
    """Only planning/inprogress follow-ups with assignees and due date."""
    if meeting.is_deleted or not meeting.end_date:
        return False
    # Check if meeting has any assignees
    if not meeting.assignees.exists():
        return False
    slug = getattr(getattr(meeting, "workflow_state", None), "slug", None)
    return slug in ACTIVE_STATE_SLUGS


def _time_suffix(meeting) -> str:
    if meeting.start_time and meeting.end_time:
        start = meeting.start_time.strftime("%I:%M %p").lstrip("0")
        end = meeting.end_time.strftime("%I:%M %p").lstrip("0")
        return f" ({start} – {end})"
    if meeting.start_time:
        return f" at {meeting.start_time.strftime('%I:%M %p').lstrip('0')}"
    return ""


def publish_meeting_due_today(meeting, *, today: date | None = None, actor_id: str | None = None) -> bool:
    if not is_notifiable_meeting(meeting):
        return False
    today = today or date.today()
    if meeting.end_date != today:
        return False

    time_suffix = _time_suffix(meeting)
    
    # Publish event for each assignee
    assignee_ids = [str(a.id) for a in meeting.assignees.all()]
    for assignee_id in assignee_ids:
        publish_event(
            EventType.MEETING_DUE_TODAY,
            ReferenceType.MEETING,
            str(meeting.id),
            payload={
                "title": meeting.title,
                "type_label": meeting.get_type_display(),
                "priority_label": meeting.get_priority_display(),
                "end_date": today.isoformat(),
                "time_window": time_suffix.strip(" ()"),
                "time_suffix": time_suffix,
                "assignee_id": assignee_id,
            },
            dedup_key=f"meeting.due_today:{meeting.id}:{assignee_id}:{today.isoformat()}",
            actor_id=actor_id,
        )
    return True


def publish_meeting_overdue(meeting, *, today: date | None = None, actor_id: str | None = None) -> bool:
    if not is_notifiable_meeting(meeting):
        return False
    today = today or date.today()
    if meeting.end_date >= today:
        return False

    days_overdue = (today - meeting.end_date).days
    if days_overdue < 1:
        return False

    # Publish event for each assignee
    assignee_ids = [str(a.id) for a in meeting.assignees.all()]
    for assignee_id in assignee_ids:
        publish_event(
            EventType.MEETING_OVERDUE,
            ReferenceType.MEETING,
            str(meeting.id),
            payload={
                "title": meeting.title,
                "type_label": meeting.get_type_display(),
                "priority_label": meeting.get_priority_display(),
                "end_date": meeting.end_date.isoformat(),
                "days_overdue": days_overdue,
                "assignee_id": assignee_id,
            },
            dedup_key=f"meeting.overdue:{meeting.id}:{assignee_id}:{today.isoformat()}",
            actor_id=actor_id,
        )
    return True


def publish_meeting_reminders(meeting, *, actor_id: str | None = None) -> None:
    """Notify assignee when a follow-up is saved and qualifies."""
    if not is_notifiable_meeting(meeting):
        return
    today = date.today()
    if meeting.end_date == today:
        publish_meeting_due_today(meeting, today=today, actor_id=actor_id)
    elif meeting.end_date < today:
        publish_meeting_overdue(meeting, today=today, actor_id=actor_id)


def scan_meeting_reminders(*, today: date | None = None) -> dict[str, int]:
    """Daily scan — due today + any overdue (planning/inprogress, assignees only)."""
    from apps.meetings.models import Meeting
    from apps.meetings.workflow import ensure_meeting_workflow

    ensure_meeting_workflow()
    today = today or date.today()
    counts = {"meetings_today": 0, "meetings_overdue": 0}

    qs = Meeting.objects.filter(
        is_deleted=False,
        end_date__isnull=False,
        workflow_state__slug__in=ACTIVE_STATE_SLUGS,
    ).prefetch_related("assignees").select_related("workflow_state")

    for meeting in qs.filter(end_date=today):
        if meeting.assignees.exists() and publish_meeting_due_today(meeting, today=today):
            counts["meetings_today"] += 1

    for meeting in qs.filter(end_date__lt=today):
        if meeting.assignees.exists() and publish_meeting_overdue(meeting, today=today):
            counts["meetings_overdue"] += 1

    return counts
