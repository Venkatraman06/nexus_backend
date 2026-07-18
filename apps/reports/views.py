from datetime import date

from django.db.models import Sum, Count, Q
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Employee
from apps.allocation.services import CapacityService
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.projects.models import Project
from apps.tickets.models import Ticket
from apps.workitems.models import WorkLog


@extend_schema(tags=["reports"], responses={200: OpenApiResponse(description="Daily log breakdown")})
class EmployeeDailyLogReport(APIView):
    """Employee's daily log breakdown."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        employee_id = request.query_params.get("employee", str(request.user.id))
        date_from = request.query_params.get("date_from", str(date.today()))
        date_to = request.query_params.get("date_to", str(date.today()))

        logs = WorkLog.objects.filter(
            employee_id=employee_id,
            is_deleted=False,
            log_date__range=[date_from, date_to],
        ).select_related("ticket__project").order_by("log_date")

        data = [
            {
                "date": str(log.log_date),
                "hours": float(log.hours),
                "is_billable": log.is_billable,
                "project": log.ticket.project.name if log.ticket_id else "",
                "ticket": log.ticket.ticket_id if log.ticket_id else "",
                "work_item": log.ticket.title if log.ticket_id else "",
                "remarks": log.remarks,
            }
            for log in logs
        ]
        total = sum(d["hours"] for d in data)
        return Response({"total_hours": total, "logs": data})


@extend_schema(tags=["reports"], responses={200: OpenApiResponse(description="Monthly utilization per employee")})
class EmployeeMonthlyUtilizationReport(APIView):
    """Monthly utilization report per employee."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.utilization"

    def get(self, request):
        year = int(request.query_params.get("year", date.today().year))
        month = int(request.query_params.get("month", date.today().month))
        employee_id = request.query_params.get("employee")

        employees = (
            Employee.objects.filter(id=employee_id)
            if employee_id
            else Employee.objects.filter(is_active=True, is_deleted=False)
        )
        return Response([
            CapacityService.employee_monthly_capacity(emp, year, month)
            for emp in employees
        ])


@extend_schema(tags=["reports"], responses={200: OpenApiResponse(description="Project progress breakdown")})
class ProjectProgressReport(APIView):
    """Project ticket progress breakdown."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.portfolio"

    def get(self, request):
        project_id = request.query_params.get("project")
        if not project_id:
            return Response({"error": "project query param required."}, status=400)

        try:
            project = Project.objects.get(id=project_id, is_deleted=False)
        except Project.DoesNotExist:
            return Response({"error": "Project not found."}, status=404)

        ticket_qs = Ticket.objects.filter(project=project, is_deleted=False)
        by_type = list(
            ticket_qs.values("type").annotate(count=Count("id")).order_by("-count")
        )
        by_priority = list(
            ticket_qs.values("priority").annotate(count=Count("id")).order_by("-count")
        )

        return Response({
            "project": {"id": str(project.id), "name": project.name, "code": project.code},
            "estimated_hours": float(project.estimated_hours),
            "logged_hours": float(project.logged_hours),
            "tickets": {
                "total": ticket_qs.count(),
                "open": ticket_qs.filter(workflow_state__is_final=False).count(),
                "done": ticket_qs.filter(workflow_state__is_final=True).count(),
                "by_type": by_type,
                "by_priority": by_priority,
            },
        })


@extend_schema(tags=["reports"], responses={200: OpenApiResponse(description="PMO portfolio summary")})
class PMOPortfolioReport(APIView):
    """Portfolio-level overview for all projects."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.portfolio"

    def get(self, request):
        projects = Project.objects.filter(is_deleted=False).select_related("client", "manager")
        data = []
        for p in projects:
            data.append({
                "id": str(p.id),
                "name": p.name,
                "code": p.code,
                "client": p.client.name if p.client else None,
                "is_active": p.is_active,
                "business_type": p.business_type.name if p.business_type else None,
                "billing_type": p.billing_type.name if p.billing_type else None,
                "start_date": str(p.start_date) if p.start_date else None,
                "end_date": str(p.end_date) if p.end_date else None,
                "estimated_hours": float(p.estimated_hours),
                "logged_hours": float(p.logged_hours),
                "manager": p.manager.full_name if p.manager else None,
            })
        return Response(data)


@extend_schema(tags=["reports"], responses={200: OpenApiResponse(description="Allocation matrix")})
class AllocationMatrixReport(APIView):
    """Employee vs. project allocation matrix."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.allocation"

    def get(self, request):
        from apps.allocation.models import Allocation
        today = date.today()
        allocations = Allocation.objects.filter(
            is_deleted=False,
            start_date__lte=today,
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=today)
        ).select_related("employee", "project")

        matrix: dict = {}
        for a in allocations:
            emp_name = a.employee.full_name
            if emp_name not in matrix:
                matrix[emp_name] = {"employee": emp_name, "projects": []}
            matrix[emp_name]["projects"].append({
                "project": a.project.name,
                "allocation_pct": float(a.allocation_percentage),
                "daily_hours": a.daily_hours,
                "start_date": str(a.start_date),
                "end_date": str(a.end_date) if a.end_date else None,
            })

        return Response(list(matrix.values()))
