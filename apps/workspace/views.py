from datetime import date, datetime

from django.db.models import Q
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import HasKeycloakPermission, IsAuthenticated
from apps.followups.models import FollowUp
from apps.todos.models import Todo


FOLLOWUP_TYPE_COLORS = {
    "EMAIL": "#6366f1",
    "CALL": "#f59e0b",
    "MEETING": "#1677ff",
    "WHATSAPP": "#22c55e",
    "SITE_VISIT": "#8b5cf6",
}

TODO_COLOR = "#039be5"


def _serialize_time(t) -> str | None:
    if not t:
        return None
    return t.strftime("%H:%M:%S")


def _followup_event(item: FollowUp) -> dict:
    slug = item.workflow_state.slug if item.workflow_state else ""
    return {
        "id": str(item.id),
        "source": "followup",
        "title": item.title,
        "subtitle": item.get_type_display(),
        "event_kind": item.type.lower(),
        "start_date": str(item.start_date) if getattr(item, "start_date", None) else (str(item.end_date) if getattr(item, "end_date", None) else None),
        "end_date": str(item.end_date) if getattr(item, "end_date", None) else None,
        "start_time": _serialize_time(item.start_time),
        "end_time": _serialize_time(item.end_time),
        "color": FOLLOWUP_TYPE_COLORS.get(item.type, "#1677ff"),
        "priority": item.priority,
        "workflow_state_slug": slug,
        "workflow_state_name": item.workflow_state.name if item.workflow_state else "",
        "assignee_name": ", ".join(a.full_name for a in item.assignees.all()) if item.assignees.exists() else None,
        "description": item.description,
        "comments": item.comments,
        "note": item.comments,
    }


def _todo_event(item: Todo) -> dict:
    slug = item.workflow_state.slug if item.workflow_state else ""
    return {
        "id": str(item.id),
        "source": "todo",
        "title": item.title,
        "subtitle": "To-Do",
        "event_kind": "todo",
        "start_date": str(item.start_date) if getattr(item, "start_date", None) else (str(item.due_date) if item.due_date else None),
        "end_date": str(item.due_date) if item.due_date else None,
        "due_date": str(item.due_date) if item.due_date else None,
        "start_time": _serialize_time(item.start_time),
        "end_time": _serialize_time(item.end_time),
        "color": TODO_COLOR,
        "priority": item.priority,
        "workflow_state_slug": slug,
        "workflow_state_name": item.workflow_state.name if item.workflow_state else "",
        "assignee_name": ", ".join(a.full_name for a in item.assignees.all()) if item.assignees.exists() else None,
        "description": item.description,
        "comments": "",
        "note": "",
    }


class WorkspaceCalendarView(APIView):
    """Unified calendar feed: todos + follow-ups for a date range."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.crm.followup.view"

    def get(self, request):
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if not date_from or not date_to:
            return Response(
                {"detail": "date_from and date_to query params are required (YYYY-MM-DD)."},
                status=400,
            )
        try:
            start = date.fromisoformat(date_from)
            end = date.fromisoformat(date_to)
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=400)

        user = request.user
        uid = user.pk
        perms = getattr(request, "user_permissions", [])
        can_followup_all = "pmt.crm.followup.view_all" in perms
        can_followup = "pmt.crm.followup.view" in perms or can_followup_all
        can_todo = can_followup
        can_todo_all = can_followup_all

        events: list[dict] = []

        if can_todo:
            todo_qs = Todo.objects.filter(
                is_deleted=False,
            ).exclude(
                workflow_state__slug__in=["done", "cancelled"]
            ).filter(
                Q(due_date__gte=start, due_date__lte=end) |
                Q(start_date__gte=start, start_date__lte=end) |
                Q(start_date__isnull=True, due_date__isnull=True)
            ).select_related("workflow_state").prefetch_related("assignees")
            if not can_todo_all:
                todo_qs = todo_qs.filter(Q(assignees__id=uid) | Q(reporter_id=uid) | Q(created_by_id=uid)).distinct()
            events.extend(_todo_event(t) for t in todo_qs)

        if can_followup:
            fu_qs = FollowUp.objects.filter(
                is_deleted=False,
            ).exclude(
                workflow_state__slug__in=["completed", "cancelled"]
            ).filter(
                # Overlap: event starts before window ends AND ends after window starts
                Q(start_date__lte=end, end_date__gte=start) |
                Q(start_date__isnull=True, end_date__gte=start, end_date__lte=end) |
                Q(end_date__isnull=True, start_date__gte=start, start_date__lte=end) |
                Q(start_date__isnull=True, end_date__isnull=True)
            ).prefetch_related("assignees").select_related("workflow_state")
            if not can_followup_all:
                fu_qs = fu_qs.filter(Q(assignees__id=uid) | Q(reporter_id=uid) | Q(created_by_id=uid)).distinct()
            events.extend(_followup_event(f) for f in fu_qs)

        events.sort(key=lambda e: (e.get("start_date") or e.get("end_date") or "", e.get("start_time") or ""))

        return Response({
            "date_from": date_from,
            "date_to": date_to,
            "count": len(events),
            "events": events,
        })
