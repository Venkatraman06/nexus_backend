from django.db.models import Q
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from apps.common.pagination import DefaultListPagination
from apps.common.permissions import HasKeycloakPermission, IsAuthenticated
from apps.common.viewsets import BaseModelViewSet
from packages.workflow.exceptions import WorkflowTransitionError

from .filters import TodoFilter
from .models import Todo
from .workflow import assign_initial_state, ensure_todo_workflow, proceed_todo
from .serializers import (
    TodoCreateSerializer,
    TodoDetailSerializer,
    TodoListSerializer,
    TodoTransitionSerializer,
)


class TodoViewSet(BaseModelViewSet):
    queryset = Todo.objects.select_related(
        "reporter", "workflow_state",
    ).prefetch_related("assignees").filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    pagination_class = DefaultListPagination
    filterset_class = TodoFilter
    search_fields = ["title", "description"]
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
            return TodoDetailSerializer
        if self.action in ("create", "update", "partial_update"):
            return TodoCreateSerializer
        return TodoListSerializer

    def _can_view_all(self) -> bool:
        user_perms = getattr(self.request, "user_permissions", [])
        return self.VIEW_ALL_PERMISSION in user_perms

    def _scoped_queryset(self, qs=None):
        qs = qs if qs is not None else super().get_queryset()
        uid = self.request.user.pk
        return qs.filter(Q(assignees__id=uid) | Q(reporter_id=uid)).distinct()

    def get_queryset(self):
        return self._scoped_queryset()

    def _can_transition(self, todo: Todo) -> bool:
        uid = self.request.user.pk
        return todo.reporter_id == uid or todo.assignees.filter(id=uid).exists()

    def list(self, request, *args, **kwargs):
        ensure_todo_workflow()
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            for todo in page:
                assign_initial_state(todo)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        for todo in queryset:
            assign_initial_state(todo)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def perform_create(self, serializer):
        ensure_todo_workflow()
        user = self.request.user
        kwargs = {}
        if not serializer.validated_data.get("reporter"):
            kwargs["reporter"] = user
        todo = serializer.save(created_by=user, updated_by=user, **kwargs)
        if not serializer.validated_data.get("assignees"):
            todo.assignees.add(user)
        assign_initial_state(todo)

    def perform_update(self, serializer):
        ensure_todo_workflow()
        user = self.request.user
        todo = serializer.save(updated_by=user)
        assign_initial_state(todo)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        ensure_todo_workflow()
        todo = self.get_object()
        if not self._can_transition(todo):
            raise PermissionDenied("Only the assignee or creator can change this todo.")

        serializer = TodoTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            proceed_todo(
                todo,
                user=request.user,
                destination_slug=serializer.validated_data["destination_state"],
                comments=serializer.validated_data.get("comments", ""),
            )
        except WorkflowTransitionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        todo.refresh_from_db()
        return Response({
            "message": "Status transitioned successfully.",
            "workflow_state_name": todo.workflow_state.name if todo.workflow_state else None,
            "workflow_state_slug": todo.workflow_state.slug if todo.workflow_state else None,
            "workflow_state_color": todo.workflow_state.color_code if todo.workflow_state else None,
        })

    @action(detail=False, methods=["get"], url_path="board")
    def board(self, request):
        ensure_todo_workflow()
        qs = self._scoped_queryset(super().get_queryset())
        qs = self.filter_queryset(qs)
        for todo in qs:
            assign_initial_state(todo)
        serializer = TodoListSerializer(qs, many=True, context={"request": request})
        columns = {}
        for item in serializer.data:
            slug = item.get("workflow_state_slug") or "unknown"
            columns.setdefault(slug, []).append(item)
        return Response({"columns": columns, "count": len(serializer.data)})
