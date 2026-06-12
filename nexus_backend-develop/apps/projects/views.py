from django.db.models import Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from packages.workflow.exceptions import WorkflowTransitionError
from packages.workflow.services import TransitionService
from .models import Client, Project, ProjectHistory
from .serializers import (
    ClientSerializer, ClientDropdownSerializer,
    ProjectListSerializer, ProjectDetailSerializer, ProjectCreateSerializer,
    ProjectTransitionSerializer, ProjectHistorySerializer, ProjectDropdownSerializer,
)
from .filters import ProjectFilter


class ClientViewSet(BaseModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    search_fields = ["name", "code", "contact_email"]
    ordering_fields = ["name", "created_at"]
    ordering = ["name"]

    PERMISSION_MAP = {
        "list":           "pmt.project.client.view",
        "retrieve":       "pmt.project.client.view",
        "create":         "pmt.project.client.create",
        "update":         "pmt.project.client.update",
        "partial_update": "pmt.project.client.update",
        "destroy":        "pmt.project.client.delete",
        "dropdown":       "pmt.project.client.view",
    }

    @action(detail=False, methods=["get"], url_path="dropdown")
    def dropdown(self, request):
        qs = Client.objects.filter(is_active=True).order_by("name")
        return Response(ClientDropdownSerializer(qs, many=True).data)


class ProjectViewSet(BaseModelViewSet):
    queryset = Project.objects.select_related(
        "client", "manager", "workflow_state", "business_type", "billing_type",
    ).filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    filterset_class = ProjectFilter
    search_fields = ["name", "code"]
    ordering_fields = ["name", "start_date", "created_at"]
    ordering = ["-created_at"]

    PERMISSION_MAP = {
        "list":               "pmt.project.view",
        "retrieve":           "pmt.project.view",
        "create":             "pmt.project.create",
        "update":             "pmt.project.update",
        "partial_update":     "pmt.project.update",
        "destroy":            "pmt.project.delete",
        "summary":            "pmt.project.view",
        "billing_summary":    "pmt.project.view",
        "generate_code":      "pmt.project.view",
        "history":            "pmt.project.view",
        "transition":         "pmt.project.update",
        "allowed_transitions":     "pmt.project.view",
        "dropdown":                "pmt.project.view",
        "allocated_employees":     "pmt.project.workitem.view",
    }

    _TRACKED_FIELDS = {
        "name":              "Project Name",
        "description":       "Description",
        "client":            "Client",
        "is_active":         "Status",
        "start_date":        "Start Date",
        "end_date":          "End Date",
        "estimated_hours":   "Estimated Hours",
        "budget":            "Project Budget",
        "manager":           "Manager",
        "workflow_state":    "Workflow State",
    }

    @staticmethod
    def _field_display(project, field: str):
        if field == "client":
            return project.client.name if project.client else None
        if field == "manager":
            return project.manager.full_name if project.manager else None
        if field == "workflow_state":
            return project.workflow_state.name if project.workflow_state else None
        if field == "is_active":
            return "Active" if project.is_active else "Inactive"
        if field == "budget":
            val = getattr(project, field, None)
            if val is None:
                return None
            return f"₹{float(val):,.2f}"
        if field == "description":
            return "(updated)" if project.description else "(cleared)"
        val = getattr(project, field, None)
        return str(val) if val is not None else None

    def _snapshot(self, project):
        return {f: self._field_display(project, f) for f in self._TRACKED_FIELDS}

    def _diff(self, old_snap, new_snap):
        changes = {}
        for field, label in self._TRACKED_FIELDS.items():
            old_val = old_snap.get(field)
            new_val = new_snap.get(field)
            if old_val != new_val:
                changes[label] = {"old": old_val, "new": new_val}
        return changes

    def get_serializer_class(self):
        if self.action == "retrieve":
            return ProjectDetailSerializer
        if self.action in ["create", "update", "partial_update"]:
            return ProjectCreateSerializer
        return ProjectListSerializer

    VIEW_ALL_PERMISSION = "pmt.project.view_all"

    def _can_view_all(self) -> bool:
        user = self.request.user
        if user.is_staff or getattr(user, "is_superuser", False):
            return True
        user_perms: list = getattr(self.request, "user_permissions", [])
        return self.VIEW_ALL_PERMISSION in user_perms

    def get_queryset(self):
        qs = super().get_queryset()
        if not self._can_view_all():
            qs = qs.filter(manager=self.request.user)
        return qs

    def perform_create(self, serializer):
        project = serializer.save()
        from django.contrib.contenttypes.models import ContentType
        from packages.workflow.models import State
        if project.workflow_state is None:
            ct = ContentType.objects.get_for_model(project)
            initial_state = State.objects.filter(content_type=ct, is_initial=True).order_by("order").first()
            if initial_state:
                project.workflow_state = initial_state
                project.save(update_fields=["workflow_state"])
        ProjectHistory.objects.create(
            project=project,
            changed_by=self.request.user,
            action="create",
            changes={label: {"old": None, "new": self._field_display(project, field)}
                     for field, label in self._TRACKED_FIELDS.items()
                     if self._field_display(project, field) is not None},
        )

        if project.manager_id:
            from apps.notifications.constants import EventType, ReferenceType
            from apps.notifications.publisher import publish_event
            publish_event(
                EventType.PROJECT_MANAGER_ASSIGNED,
                ReferenceType.PROJECT,
                str(project.id),
                payload={
                    "project_name": project.name,
                    "manager_id": str(project.manager_id),
                },
                actor_id=str(self.request.user.id),
                async_delivery=True,
            )

    def perform_update(self, serializer):
        old_snap = self._snapshot(serializer.instance)
        old_manager_id = serializer.instance.manager_id
        project = serializer.save()
        new_snap = self._snapshot(project)
        changes = self._diff(old_snap, new_snap)
        if changes:
            ProjectHistory.objects.create(
                project=project,
                changed_by=self.request.user,
                action="update",
                changes=changes,
            )

        if project.manager_id and project.manager_id != old_manager_id:
            from apps.notifications.constants import EventType, ReferenceType
            from apps.notifications.publisher import publish_event
            publish_event(
                EventType.PROJECT_MANAGER_ASSIGNED,
                ReferenceType.PROJECT,
                str(project.id),
                payload={
                    "project_name": project.name,
                    "manager_id": str(project.manager_id),
                },
                actor_id=str(self.request.user.id),
                async_delivery=True,
            )

    @action(detail=False, methods=["get"], url_path="dropdown")
    def dropdown(self, request):
        qs = Project.objects.filter(is_deleted=False, is_active=True).order_by("name")
        return Response(ProjectDropdownSerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="allocated-employees")
    def allocated_employees(self, request, pk=None):
        """Return employees actively allocated to this project (date-checked)."""
        from datetime import date
        from django.db.models import Q
        from apps.allocation.models import Allocation

        project = self.get_object()
        today = date.today()

        allocations = Allocation.objects.filter(
            project=project,
            is_deleted=False,
            start_date__lte=today,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).select_related("employee").order_by("employee__first_name")

        data = [
            {
                "id": str(a.employee.id),
                "full_name": a.employee.full_name,
                "employee_code": a.employee.employee_code,
                "designation": a.employee.designation_ref.name if a.employee.designation_ref_id else "",
            }
            for a in allocations
            if not a.employee.is_deleted and a.employee.is_active
        ]
        return Response(data)

    @action(detail=False, methods=["get"], url_path="generate-code")
    def generate_code(self, request):
        from apps.master.models import BusinessType as MasterBusinessType
        business_type_id = request.query_params.get("business_type_id")
        business_type = None
        if business_type_id:
            try:
                business_type = MasterBusinessType.objects.get(id=business_type_id)
            except MasterBusinessType.DoesNotExist:
                pass
        code = Project.generate_code(business_type=business_type)
        return Response({"code": code})

    @action(detail=True, methods=["get"], url_path="history")
    def history(self, request, pk=None):
        project = self.get_object()
        qs = ProjectHistory.objects.filter(project=project).select_related("changed_by")
        return Response(ProjectHistorySerializer(qs, many=True).data)

    @action(detail=True, methods=["get"], url_path="allowed-transitions")
    def allowed_transitions(self, request, pk=None):
        project = self.get_object()
        transitions = TransitionService.get_allowed_transitions(project, request.user)
        data = [
            {
                "id": str(t.id),
                "label": t.label,
                "destination_state": str(t.destination_state_id),
                "destination_state_slug": t.destination_state.slug,
                "destination_state_name": t.destination_state.name,
                "destination_state_color": t.destination_state.color_code,
                "group_names": [g.name for g in t.groups.all()],
            }
            for t in transitions
        ]
        return Response(data)

    @action(detail=True, methods=["post"], url_path="transition")
    def transition(self, request, pk=None):
        project = self.get_object()
        serializer = ProjectTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        dest_slug = serializer.validated_data["destination_state"]
        comments = serializer.validated_data.get("comments", "")
        manager_id = serializer.validated_data.get("manager")

        old_state_name = project.workflow_state.name if project.workflow_state else None
        old_manager_name = project.manager.full_name if project.manager else None
        try:
            project.proceed(
                user=request.user,
                destination_slug=dest_slug,
                comments=comments,
            )
        except WorkflowTransitionError as exc:
            return Response({"error": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        changes = {}
        new_state_name = project.workflow_state.name if project.workflow_state else None
        if old_state_name != new_state_name:
            changes["Workflow State"] = {"old": old_state_name, "new": new_state_name}

        if manager_id is not None:
            from apps.accounts.models import Employee
            try:
                new_manager = Employee.objects.get(id=manager_id)
                project.manager = new_manager
                project.save(update_fields=["manager"])
                new_manager_name = new_manager.full_name
                if old_manager_name != new_manager_name:
                    changes["Manager"] = {"old": old_manager_name, "new": new_manager_name}
            except Employee.DoesNotExist:
                pass

        if changes:
            ProjectHistory.objects.create(
                project=project,
                changed_by=request.user,
                action="update",
                changes=changes,
            )

        return Response({
            "message": "Workflow transitioned successfully.",
            "workflow_state": str(project.workflow_state_id) if project.workflow_state_id else None,
            "workflow_state_name": new_state_name,
            "workflow_state_slug": project.workflow_state.slug if project.workflow_state else None,
            "workflow_state_color": project.workflow_state.color_code if project.workflow_state else None,
            "manager": str(project.manager_id) if project.manager_id else None,
            "manager_name": project.manager.full_name if project.manager else None,
        })

    @action(detail=True, methods=["get"], url_path="summary")
    def summary(self, request, pk=None):
        from apps.tickets.models import Ticket
        project = self.get_object()
        total_tickets = Ticket.objects.filter(project=project, is_deleted=False).count()
        open_tickets = Ticket.objects.filter(
            project=project, is_deleted=False, workflow_state__is_final=False
        ).count()

        return Response({
            "project": ProjectDetailSerializer(project).data,
            "total_tickets": total_tickets,
            "open_tickets": open_tickets,
            "estimated_hours": float(project.estimated_hours),
            "budget": float(project.budget),
        })

    @action(detail=True, methods=["get"], url_path="billing-summary")
    def billing_summary(self, request, pk=None):
        from apps.payment.budget_service import project_budget_summary
        project = self.get_object()
        return Response(project_budget_summary(project))
