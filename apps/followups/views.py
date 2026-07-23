from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.pagination import DefaultListPagination
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
    queryset = FollowUp.objects.prefetch_related(
        "assignees"
    ).select_related(
        "reporter", "workflow_state",
    ).filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    pagination_class = DefaultListPagination
    filterset_class = FollowUpFilter
    search_fields = ["title", "description", "comments"]
    ordering_fields = ["created_at", "start_date", "end_date", "title"]
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
        """Only when view_all=true query param is explicitly passed AND user has permission."""
        view_all_param = self.request.query_params.get("view_all") == "true"
        user_perms = getattr(self.request, "user_permissions", [])
        return view_all_param and (self.VIEW_ALL_PERMISSION in user_perms)

    def _scoped_queryset(self, qs=None):
        """Assignee or reporter (creator) only, unless view_all."""
        qs = qs if qs is not None else super().get_queryset()
        
        # Exclude old meetings from the follow-up module
        qs = qs.exclude(type="MEETING")
        
        if self._can_view_all():
            return qs
        uid = self.request.user.pk
        return qs.filter(Q(assignees__id=uid) | Q(reporter_id=uid) | Q(created_by_id=uid)).distinct()

    def get_queryset(self):
        return self._scoped_queryset()

    def _can_transition(self, followup: FollowUp) -> bool:
        if self._can_view_all():
            return True
        user = self.request.user
        user_perms = getattr(self.request, "user_permissions", [])
        if "pmt.crm.followup.transition" in user_perms:
            return True
        uid = user.pk
        return followup.assignees.filter(id=uid).exists() or followup.reporter_id == uid or followup.created_by_id == uid

    def list(self, request, *args, **kwargs):
        ensure_followup_workflow()
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            for followup in page:
                assign_initial_state(followup)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        for followup in queryset:
            assign_initial_state(followup)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        ensure_followup_workflow()
        user = self.request.user
        kwargs = {}
        if not serializer.validated_data.get("reporter"):
            kwargs["reporter"] = user
        
        followup = serializer.save(created_by=user, updated_by=user, **kwargs)
        
        # If no assignees provided, assign to the current user
        if not followup.assignees.exists():
            followup.assignees.add(user)
        
        assign_initial_state(followup)
        followup.refresh_from_db()
        
        # Notify assignees
        assignee_ids = [str(a.id) for a in followup.assignees.all()]
        assignee_ids = [aid for aid in assignee_ids if aid != str(user.id)]
        if assignee_ids:
            from apps.notifications.publisher import publish_event
            from apps.notifications.constants import EventType, ReferenceType
            publish_event(
                event_type=EventType.FOLLOWUP_ASSIGNED,
                reference_type=ReferenceType.FOLLOWUP,
                reference_id=str(followup.id),
                payload={"title": followup.title},
                actor_id=str(user.id),
                recipient_ids=assignee_ids,
                async_delivery=True,
            )
            
        from .notifications import publish_followup_reminders
        publish_followup_reminders(followup, actor_id=str(user.pk))

    def perform_update(self, serializer):
        ensure_followup_workflow()
        user = self.request.user
        
        instance = self.get_object()
        old_assignee_ids = set(str(a.id) for a in instance.assignees.all())
        
        followup = serializer.save(updated_by=user)
        assign_initial_state(followup)
        followup.refresh_from_db()
        
        # Notify new assignees
        new_assignee_ids = [str(a.id) for a in followup.assignees.all()]
        new_assignees = [aid for aid in new_assignee_ids if aid not in old_assignee_ids and aid != str(user.id)]
        if new_assignees:
            from apps.notifications.publisher import publish_event
            from apps.notifications.constants import EventType, ReferenceType
            publish_event(
                event_type=EventType.FOLLOWUP_ASSIGNED,
                reference_type=ReferenceType.FOLLOWUP,
                reference_id=str(followup.id),
                payload={"title": followup.title},
                actor_id=str(user.id),
                recipient_ids=new_assignees,
                async_delivery=True,
            )

        # Notify existing assignees + reporter about comments/updates
        all_recipients = set(new_assignee_ids)
        if followup.reporter_id:
            all_recipients.add(str(followup.reporter_id))
        all_recipients.discard(str(user.id))

        if all_recipients:
            from apps.notifications.publisher import publish_event
            from apps.notifications.constants import EventType, ReferenceType
            is_comment = "comments" in serializer.validated_data and serializer.validated_data["comments"] != instance.comments
            event_type = EventType.FOLLOWUP_COMMENTED if is_comment else EventType.FOLLOWUP_UPDATED
            publish_event(
                event_type=event_type,
                reference_type=ReferenceType.FOLLOWUP,
                reference_id=str(followup.id),
                payload={"title": followup.title, "actor_name": user.full_name},
                actor_id=str(user.id),
                recipient_ids=list(all_recipients),
                async_delivery=True,
            )
            
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
                assignees = item.get("assignees", [])
                reporter = item.get("reporter")
                # Check if user is one of the assignees or the reporter
                is_assignee = any(str(a) == str(uid) for a in assignees)
                if not is_assignee and str(reporter) != str(uid):
                    continue
            slug = item.get("workflow_state_slug") or "unknown"
            columns.setdefault(slug, []).append(item)
        visible_count = sum(len(v) for v in columns.values())
        return Response({"columns": columns, "count": visible_count})


class MeetingViewSet(FollowUpViewSet):
    def get_queryset(self):
        qs = super().get_queryset()
        return qs.filter(type="MEETING")

    def perform_create(self, serializer):
        serializer.validated_data["type"] = "MEETING"
        super().perform_create(serializer)

