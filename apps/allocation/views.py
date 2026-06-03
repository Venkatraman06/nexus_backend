from datetime import date

from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import Employee
from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from .models import Allocation
from .serializers import AllocationSerializer, AllocationCreateSerializer, EmployeeCapacitySerializer
from .services import CapacityService


class AllocationViewSet(BaseModelViewSet):
    queryset = Allocation.objects.select_related("employee", "project").filter(is_deleted=False)
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    search_fields = ["employee__first_name", "employee__last_name", "project__name"]
    ordering_fields = ["start_date", "allocation_percentage", "created_at"]
    ordering = ["-start_date"]
    filterset_fields = ["employee", "project"]

    PERMISSION_MAP = {
        "list":              "pmt.project.allocation.view",
        "retrieve":          "pmt.project.allocation.view",
        "create":            "pmt.project.allocation.create",
        "update":            "pmt.project.allocation.update",
        "partial_update":    "pmt.project.allocation.update",
        "destroy":           "pmt.project.allocation.delete",
        "employee_capacity": "pmt.project.allocation.view",
        "team_pipeline":     "pmt.project.allocation.view",
    }

    def get_serializer_class(self):
        if self.action in ["create", "update", "partial_update"]:
            return AllocationCreateSerializer
        return AllocationSerializer

    @action(detail=False, methods=["get"], url_path="employee-capacity")
    def employee_capacity(self, request):
        year = int(request.query_params.get("year", date.today().year))
        month = int(request.query_params.get("month", date.today().month))
        employee_id = request.query_params.get("employee")

        employees = (
            Employee.objects.filter(id=employee_id)
            if employee_id
            else Employee.objects.filter(is_active=True, is_deleted=False)
        )

        results = [
            CapacityService.employee_monthly_capacity(emp, year, month)
            for emp in employees
        ]
        return Response(results)

    @action(detail=False, methods=["get"], url_path="team-pipeline")
    def team_pipeline(self, request):
        today = date.today()
        results = []
        for emp in Employee.objects.filter(is_active=True, is_deleted=False):
            months = []
            for delta in range(3):
                m = today.month + delta
                y = today.year
                if m > 12:
                    m -= 12
                    y += 1
                months.append(CapacityService.employee_monthly_capacity(emp, y, m))
            results.append({"employee": emp.full_name, "pipeline": months})
        return Response(results)
