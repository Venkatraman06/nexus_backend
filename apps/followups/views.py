from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.permissions import HasKeycloakPermission, IsAuthenticated
from apps.common.viewsets import BaseModelViewSet
from packages.workflow.exceptions import WorkflowTransitionError

from .filters import FollowUpFilter
from .models import FollowUp
from .workflow import assign_initial_state, ensure_followup_workflow, proceed_followup
from .serializers import (
    FollowUpCreateSerializer,
    FollowUpDetailSerializer,
    FollowUpListSerializer,
    FollowUpTransitionSerializer,
)


class FollowUpViewSet(BaseModelViewSet):
    queryset = FollowUp.objects.select_related(
        "assignee", "reporter", "workflow_state",
    ).filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    filterset_class = FollowUpFilter
    search_fields = ["title", "description", "comments"]
    ordering_fields = ["created_at", "due_date", "title"]
    ordering = ["-created_at"]

    PERMISSION_MAP = {
        "list":           "pmt.crm.followup.view",
        "retrieve":       "pmt.crm.followup.view",
        "create":         "pmt.crm.followup.create",
        "update":         "pmt.crm.followup.update",
        "partial_update": "pmt.crm.followup.update",
        "destroy":        "pmt.crm.followup.delete",
        "transition":     "pmt.crm.followup.transition",
        "board":          "pmt.crm.followup.view",
    }

    VIEW_ALL_PERMISSION = "pmt.crm.followup.view_all"

    def get_serializer_class(self):
        if self.action == "retrieve":
            return FollowUpDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return FollowUpCreateSerializer
        return FollowUpListSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx

    def _can_view_all(self) -> bool:
        """Only users with explicit view_all permission see every follow-up."""
        user_perms = getattr(self.request, "user_permissions", [])
        return self.VIEW_ALL_PERMISSION in user_perms

    def _scoped_queryset(self, qs=None):
        """Assignee or reporter (creator) only, unless view_all."""
        qs = qs if qs is not None else super().get_queryset()
        if self._can_view_all():
            return qs
        uid = self.request.user.pk
        return qs.filter(Q(assignee_id=uid) | Q(reporter_id=uid))

    def get_queryset(self):
        return self._scoped_queryset()

    def _can_transition(self, followup: FollowUp) -> bool:
        if self._can_view_all():
            return True
        user = self.request.user
        uid = user.pk
        return followup.assignee_id == uid or followup.reporter_id == uid

    def list(self, request, *args, **kwargs):
        ensure_followup_workflow()
        for followup in self.filter_queryset(self.get_queryset()):
            assign_initial_state(followup)
        return super().list(request, *args, **kwargs)

    def perform_create(self, serializer):
        ensure_followup_workflow()
        user = self.request.user
        kwargs = {}
        if not serializer.validated_data.get("reporter"):
            kwargs["reporter"] = user
        if not serializer.validated_data.get("assignee"):
            kwargs["assignee"] = user
        followup = serializer.save(created_by=user, updated_by=user, **kwargs)
        assign_initial_state(followup)
        followup.refresh_from_db()
        from .notifications import publish_followup_reminders
        publish_followup_reminders(followup, actor_id=str(user.pk))

    def perform_update(self, serializer):
        ensure_followup_workflow()
        user = self.request.user
        followup = serializer.save(updated_by=user)
        assign_initial_state(followup)
        followup.refresh_from_db()
        from .notifications import publish_followup_reminders
        publish_followup_reminders(followup, actor_id=str(user.pk))

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        ensure_followup_workflow()
        followup = self.get_object()
        if not self._can_transition(followup):
            raise PermissionDenied(
                "Only the assignee or reporter of this follow-up can change its status."
            )

        serializer = FollowUpTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            proceed_followup(
                followup,
                user=request.user,
                destination_slug=serializer.validated_data["destination_state"],
                comments=serializer.validated_data.get("comments", ""),
            )
        except WorkflowTransitionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        followup.refresh_from_db()
        return Response({
            "message": "Status transitioned successfully.",
            "workflow_state_name": followup.workflow_state.name if followup.workflow_state else None,
            "workflow_state_slug": followup.workflow_state.slug if followup.workflow_state else None,
            "workflow_state_color": followup.workflow_state.color_code if followup.workflow_state else None,
        })

    @action(detail=False, methods=["get"], url_path="board")
    def board(self, request):
        ensure_followup_workflow()
        qs = self._scoped_queryset(super().get_queryset())
        qs = self.filter_queryset(qs)
        for followup in qs:
            assign_initial_state(followup)
        serializer = FollowUpListSerializer(qs, many=True, context={"request": request})
        columns = {}
        uid = request.user.pk
        view_all = self._can_view_all()
        for item in serializer.data:
            if not view_all:
                assignee = item.get("assignee")
                reporter = item.get("reporter")
                if str(assignee) != str(uid) and str(reporter) != str(uid):
                    continue
            slug = item.get("workflow_state_slug") or "unknown"
            columns.setdefault(slug, []).append(item)
        visible_count = sum(len(v) for v in columns.values())
        return Response({"columns": columns, "count": visible_count})
