"""
Timesheet views — employee-centric views of their time logs.
"""
from datetime import date, timedelta

from django.db.models import Sum
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Employee
from apps.allocation.services import CapacityService
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.workitems.models import WorkLog
from apps.workitems.serializers import WorkLogSerializer, WorkLogCreateSerializer


@extend_schema(tags=["timesheets"], responses={200: OpenApiResponse(description="My timesheet logs")})
class MyTimesheetView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        date_from = request.query_params.get("date_from", str(date.today() - timedelta(days=7)))
        date_to = request.query_params.get("date_to", str(date.today()))

        logs = WorkLog.objects.filter(
            employee=request.user,
            is_deleted=False,
            log_date__range=[date_from, date_to],
        ).select_related("ticket__project").order_by("-log_date")

        total = float(logs.aggregate(t=Sum("hours"))["t"] or 0)
        return Response({
            "total_hours": total,
            "logs": WorkLogSerializer(logs, many=True).data,
        })

    def post(self, request):
        perms = getattr(request, "user_permissions", [])
        if not (
            request.user.is_staff
            or getattr(request.user, "is_superuser", False)
            or "pmt.project.timesheet.create" in perms
        ):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("pmt.project.timesheet.create required")
        serializer = WorkLogCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        log = serializer.save()
        return Response(WorkLogSerializer(log).data, status=201)


@extend_schema(tags=["timesheets"], responses={200: OpenApiResponse(description="Weekly timesheet summary")})
class TimesheetWeeklyView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        weeks = []
        for i in range(4):
            ws = start_of_week - timedelta(weeks=i)
            we = ws + timedelta(days=4)
            logs = WorkLog.objects.filter(
                employee=request.user, is_deleted=False, log_date__range=[ws, we]
            )
            total = float(logs.aggregate(t=Sum("hours"))["t"] or 0)
            billable = float(logs.filter(is_billable=True).aggregate(t=Sum("hours"))["t"] or 0)
            weeks.append({
                "week_start": str(ws),
                "week_end": str(we),
                "total_hours": total,
                "billable_hours": billable,
                "non_billable_hours": total - billable,
            })
        return Response(weeks)


@extend_schema(tags=["timesheets"], responses={200: OpenApiResponse(description="Team timesheet utilization summary")})
class TeamTimesheetView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.utilization"

    def get(self, request):
        year = int(request.query_params.get("year", date.today().year))
        month = int(request.query_params.get("month", date.today().month))
        employees = Employee.objects.filter(is_active=True, is_deleted=False)
        return Response([
            CapacityService.employee_monthly_capacity(emp, year, month)
            for emp in employees
        ])
