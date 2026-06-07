from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from rest_framework.response import Response

from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from packages.workflow.exceptions import WorkflowTransitionError
from .models import Ticket, TicketAttachment, TicketComment, TicketHistory
from .serializers import (
    TicketListSerializer, TicketDetailSerializer, TicketCreateSerializer,
    TicketTransitionSerializer, TicketAttachmentSerializer,
    TicketCommentSerializer, TicketHistorySerializer,
)
from .filters import TicketFilter

_TRACKED_FIELDS = {
    "title":            "Title",
    "description":      "Description",
    "type":             "Type",
    "priority":         "Priority",
    "due_date":         "Due Date",
    "original_estimate":"Original Estimate",
    "assignee":         "Assignee",
    "reporter":         "Reporter",
    "approved":         "Approved",
    "parent":           "Parent",
    "workflow_state":   "Status",
}


def _field_display(ticket, field: str):
    if field == "assignee":
        return ticket.assignee.full_name if ticket.assignee else None
    if field == "reporter":
        return ticket.reporter.full_name if ticket.reporter else None
    if field == "workflow_state":
        return ticket.workflow_state.name if ticket.workflow_state else None
    if field == "parent":
        return ticket.parent.ticket_id if ticket.parent else None
    if field == "approved":
        return "Yes" if ticket.approved else "No"
    if field == "description":
        return "(updated)" if ticket.description else "(cleared)"
    val = getattr(ticket, field, None)
    return str(val) if val is not None else None


def _snapshot(ticket):
    return {f: _field_display(ticket, f) for f in _TRACKED_FIELDS}


def _diff(old_snap, new_snap):
    changes = {}
    for field, label in _TRACKED_FIELDS.items():
        old_val = old_snap.get(field)
        new_val = new_snap.get(field)
        if old_val != new_val:
            changes[label] = {"old": old_val, "new": new_val}
    return changes


class TicketViewSet(BaseModelViewSet):
    queryset = Ticket.objects.select_related(
        "project", "assignee", "reporter", "workflow_state", "parent",
    ).prefetch_related("notify_users").filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    filterset_class = TicketFilter
    search_fields = ["title", "ticket_id", "description"]
    ordering_fields = ["created_at", "priority", "due_date", "ticket_id"]
    ordering = ["-created_at"]

    # Reuse workitem permission strings — these are already granted in Keycloak
    # for project manager / member roles, avoiding the need to seed new permissions.
    PERMISSION_MAP = {
        "list":             "pmt.project.workitem.view",
        "retrieve":         "pmt.project.workitem.view",
        "create":           "pmt.project.workitem.create",
        "update":           "pmt.project.workitem.update",
        "partial_update":   "pmt.project.workitem.update",
        "destroy":          "pmt.project.workitem.delete",
        "transition":       "pmt.project.workitem.transition",
        "attachments":      "pmt.project.workitem.view",
        "delete_attachment": "pmt.project.workitem.update",
        "comments":         "pmt.project.workitem.view",
        "comment_detail":   "pmt.project.workitem.view",
        "history":          "pmt.project.workitem.view",
        "children":         "pmt.project.workitem.view",
    }

    def get_serializer_class(self):
        if self.action == "retrieve":
            return TicketDetailSerializer
        if self.action in ["create", "update", "partial_update"]:
            return TicketCreateSerializer
        return TicketListSerializer

    VIEW_ALL_PERMISSION = "pmt.project.view_all"

    def _can_view_all(self) -> bool:
        user = self.request.user
        if user.is_staff or getattr(user, "is_superuser", False):
            return True
        user_perms: list = getattr(self.request, "user_permissions", [])
        return self.VIEW_ALL_PERMISSION in user_perms

    def get_queryset(self):
        from datetime import date
        from django.db.models import Q
        from apps.allocation.models import Allocation
        from apps.projects.models import Project

        qs = super().get_queryset()

        # PMO / admin / view_all permission → unrestricted
        if self._can_view_all():
            return qs

        user = self.request.user
        today = date.today()

        # Projects the user manages
        managed_project_ids = Project.objects.filter(
            manager=user, is_deleted=False
        ).values_list("id", flat=True)

        # Projects the user is actively allocated to (date-checked)
        allocated_project_ids = Allocation.objects.filter(
            employee=user,
            is_deleted=False,
            start_date__lte=today,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).values_list("project_id", flat=True)

        accessible = set(managed_project_ids) | set(allocated_project_ids)
        return qs.filter(project_id__in=accessible)

    def _can_access_project(self, project_id) -> bool:
        """Return True if request.user may create/edit tickets in this project."""
        from datetime import date
        from django.db.models import Q
        from apps.allocation.models import Allocation
        from apps.projects.models import Project

        if self._can_view_all():
            return True

        user = self.request.user

        today = date.today()
        is_manager = Project.objects.filter(id=project_id, manager=user, is_deleted=False).exists()
        if is_manager:
            return True

        return Allocation.objects.filter(
            employee=user, project_id=project_id, is_deleted=False,
            start_date__lte=today,
        ).filter(Q(end_date__isnull=True) | Q(end_date__gte=today)).exists()

    @staticmethod
    def _ensure_ticket_workflow_states():
        """
        Clone workflow states (and transitions) from workitems.workitem to
        tickets.ticket the first time — runs once, skipped afterwards.
        """
        from django.contrib.contenttypes.models import ContentType
        from packages.workflow.models import State, Transition

        ticket_ct = ContentType.objects.get(app_label="tickets", model="ticket")

        # Already configured — nothing to do
        if State.objects.filter(content_type=ticket_ct).exists():
            return

        # Source: the workitem states that are already in the DB
        try:
            workitem_ct = ContentType.objects.get(app_label="workitems", model="workitem")
        except ContentType.DoesNotExist:
            return

        source_states = list(State.objects.filter(content_type=workitem_ct).order_by("order"))
        if not source_states:
            return

        # Clone states
        old_id_to_new = {}
        for s in source_states:
            new_state = State.objects.create(
                content_type=ticket_ct,
                name=s.name,
                slug=f"ticket-{s.slug}",
                label=s.label,
                color_code=s.color_code,
                order=s.order,
                is_initial=s.is_initial,
                is_final=s.is_final,
            )
            old_id_to_new[s.id] = new_state

        # Clone transitions
        for t in Transition.objects.filter(content_type=workitem_ct):
            src = old_id_to_new.get(t.source_state_id)
            dst = old_id_to_new.get(t.destination_state_id)
            if src and dst:
                new_t = Transition.objects.create(
                    content_type=ticket_ct,
                    source_state=src,
                    destination_state=dst,
                    label=t.label,
                )
                new_t.groups.set(t.groups.all())

    def perform_create(self, serializer):
        from rest_framework.exceptions import PermissionDenied
        from django.contrib.contenttypes.models import ContentType
        from packages.workflow.models import State

        user = self.request.user
        project = serializer.validated_data.get("project")
        if project and not self._can_access_project(project.id):
            raise PermissionDenied("You are not allocated to this project.")

        # Seed ticket workflow states from workitem states on first use
        self._ensure_ticket_workflow_states()

        kwargs = {}
        if not serializer.validated_data.get("reporter"):
            kwargs["reporter"] = user
        if not serializer.validated_data.get("assignee"):
            kwargs["assignee"] = user
        ticket = serializer.save(**kwargs)

        # Auto-assign initial workflow state
        if ticket.workflow_state is None:
            ticket_ct = ContentType.objects.get_for_model(ticket)
            initial_state = State.objects.filter(
                content_type=ticket_ct, is_initial=True
            ).order_by("order").first()
            if initial_state:
                ticket.workflow_state = initial_state
                ticket.save(update_fields=["workflow_state"])

        TicketHistory.objects.create(
            ticket=ticket,
            changed_by=user,
            action="create",
            changes={label: {"old": None, "new": _field_display(ticket, field)}
                     for field, label in _TRACKED_FIELDS.items()
                     if _field_display(ticket, field) is not None},
        )

        if ticket.assignee_id:
            from apps.notifications.constants import EventType, ReferenceType
            from apps.notifications.publisher import publish_event
            publish_event(
                EventType.TICKET_ASSIGNED,
                ReferenceType.TICKET,
                str(ticket.id),
                payload={
                    "ticket_id": ticket.ticket_id,
                    "title": ticket.title,
                    "project_name": ticket.project.name if ticket.project else "",
                    "assignee_id": str(ticket.assignee_id),
                },
                actor_id=str(user.id),
                async_delivery=True,
            )

    def perform_update(self, serializer):
        old_snap = _snapshot(serializer.instance)
        old_assignee_id = serializer.instance.assignee_id
        ticket = serializer.save()
        new_snap = _snapshot(ticket)
        changes = _diff(old_snap, new_snap)
        if changes:
            TicketHistory.objects.create(
                ticket=ticket,
                changed_by=self.request.user,
                action="update",
                changes=changes,
            )

        if ticket.assignee_id and ticket.assignee_id != old_assignee_id:
            from apps.notifications.constants import EventType, ReferenceType
            from apps.notifications.publisher import publish_event
            publish_event(
                EventType.TICKET_ASSIGNED,
                ReferenceType.TICKET,
                str(ticket.id),
                payload={
                    "ticket_id": ticket.ticket_id,
                    "title": ticket.title,
                    "project_name": ticket.project.name if ticket.project else "",
                    "assignee_id": str(ticket.assignee_id),
                },
                actor_id=str(self.request.user.id),
                async_delivery=True,
            )

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        from rest_framework.exceptions import PermissionDenied
        ticket = self.get_object()

        # Only the assignee, reporter, or a user with view_all (PMO/admin) may transition
        if not self._can_view_all():
            user = request.user
            is_assignee = ticket.assignee_id and str(ticket.assignee_id) == str(user.id)
            is_reporter = ticket.reporter_id and str(ticket.reporter_id) == str(user.id)
            if not (is_assignee or is_reporter):
                raise PermissionDenied(
                    "Only the assignee or reporter of this ticket can change its status."
                )

        serializer = TicketTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        old_state_name = ticket.workflow_state.name if ticket.workflow_state else None
        try:
            ticket.proceed(
                user=request.user,
                destination_slug=serializer.validated_data["destination_state"],
                comments=serializer.validated_data.get("comments", ""),
            )
        except WorkflowTransitionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        new_state_name = ticket.workflow_state.name if ticket.workflow_state else None
        if old_state_name != new_state_name:
            TicketHistory.objects.create(
                ticket=ticket,
                changed_by=request.user,
                action="update",
                changes={"Status": {"old": old_state_name, "new": new_state_name}},
            )

        return Response({
            "message": "Status transitioned successfully.",
            "workflow_state_name": new_state_name,
            "workflow_state_slug": ticket.workflow_state.slug if ticket.workflow_state else None,
            "workflow_state_color": ticket.workflow_state.color_code if ticket.workflow_state else None,
        })

    @action(detail=True, methods=["get", "post"], url_path="attachments",
            parser_classes=[MultiPartParser, FormParser, JSONParser])
    def attachments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == "GET":
            return Response(
                TicketAttachmentSerializer(ticket.attachments.all(), many=True).data
            )
        serializer = TicketAttachmentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ticket=ticket, uploaded_by=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path="attachments/(?P<attachment_id>[^/.]+)")
    def delete_attachment(self, request, pk=None, attachment_id=None):
        ticket = self.get_object()
        try:
            attachment = ticket.attachments.get(id=attachment_id)
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except TicketAttachment.DoesNotExist:
            return Response({"error": "Attachment not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=True, methods=["get", "post"], url_path="comments")
    def comments(self, request, pk=None):
        ticket = self.get_object()
        if request.method == "GET":
            qs = ticket.comments.filter(is_deleted=False).select_related("author")
            return Response(TicketCommentSerializer(qs, many=True).data)
        serializer = TicketCommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(ticket=ticket, author=request.user)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["patch", "delete"],
            url_path="comments/(?P<comment_id>[^/.]+)")
    def comment_detail(self, request, pk=None, comment_id=None):
        ticket = self.get_object()
        try:
            comment = ticket.comments.get(id=comment_id, is_deleted=False)
        except TicketComment.DoesNotExist:
            return Response({"error": "Comment not found."}, status=status.HTTP_404_NOT_FOUND)

        if request.method == "DELETE":
            if comment.author != request.user and not request.user.is_staff:
                return Response({"error": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
            comment.is_deleted = True
            comment.save(update_fields=["is_deleted"])
            return Response(status=status.HTTP_204_NO_CONTENT)

        if comment.author != request.user and not request.user.is_staff:
            return Response({"error": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        serializer = TicketCommentSerializer(comment, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        comment = serializer.save(is_edited=True)
        return Response(TicketCommentSerializer(comment).data)

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        ticket = self.get_object()
        qs = ticket.history.select_related("changed_by")
        workflow_history = [
            {
                "id": str(p.id),
                "action": "transition",
                "changes": {
                    "Status": {
                        "old": p.previous_state.name if p.previous_state else None,
                        "new": p.state.name if p.state else None,
                    }
                },
                "changed_by_name": p.transitioned_by.full_name if p.transitioned_by else "System",
                "changed_at": p.created_at.isoformat() if p.created_at else None,
                "comments": p.comments,
            }
            for p in ticket.state_history
        ]
        field_history = TicketHistorySerializer(qs, many=True).data
        combined = sorted(
            list(field_history) + workflow_history,
            key=lambda x: x["changed_at"] or "",
            reverse=True,
        )
        return Response(combined)

    @action(detail=True, methods=["get"], url_path="children")
    def children(self, request, pk=None):
        ticket = self.get_object()
        qs = ticket.children.filter(is_deleted=False).select_related(
            "assignee", "workflow_state"
        )
        return Response(TicketListSerializer(qs, many=True).data)
