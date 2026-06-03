from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from .models import WorkLog
from .serializers import WorkLogSerializer, WorkLogCreateSerializer
from .filters import WorkLogFilter


class WorkLogViewSet(BaseModelViewSet):
    queryset = WorkLog.objects.select_related(
        "employee", "ticket__project"
    ).filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    filterset_class = WorkLogFilter
    search_fields = ["ticket__title", "ticket__ticket_id", "remarks"]
    ordering_fields = ["log_date", "hours", "created_at"]
    ordering = ["-log_date"]

    PERMISSION_MAP = {
        "list":           "pmt.project.timesheet.view",
        "retrieve":       "pmt.project.timesheet.view",
        "create":         "pmt.project.timesheet.create",
        "update":         "pmt.project.timesheet.update",
        "partial_update": "pmt.project.timesheet.update",
        "destroy":        "pmt.project.timesheet.delete",
    }

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return WorkLogCreateSerializer
        return WorkLogSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if not self.request.user.is_staff:
            employee_filter = self.request.query_params.get("employee")
            if not employee_filter:
                qs = qs.filter(employee=self.request.user)
        return qs
