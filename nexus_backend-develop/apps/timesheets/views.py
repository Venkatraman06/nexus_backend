"""
Tempo-style timesheet APIs — employee logging, weekly submission, manager review.
"""
from datetime import date, timedelta

from django.db.models import Q, Sum
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.allocation.services import CapacityService
from apps.common.permissions import HasKeycloakPermission, IsAuthenticated
from apps.workitems.models import WorkLog
from apps.workitems.serializers import WorkLogSerializer

from apps.common.constants import TimesheetStatus

from .models import WeeklyTimesheet
from .serializers import (
    BulkReviewSerializer,
    CopyDaySerializer,
    CopyWeekSerializer,
    LoggableTicketSerializer,
    ReviewTimesheetSerializer,
    SubmitTimesheetSerializer,
    TimesheetConfigSerializer,
    TimesheetWeekSerializer,
    WeeklyTimesheetSerializer,
    WorkLogDetailSerializer,
)
from .services import (
    approve_timesheet,
    can_review_timesheet,
    copy_logs_from_date,
    copy_logs_from_week,
    get_daily_capacity,
    get_loggable_dates,
    get_loggable_tickets_with_hints,
    get_or_create_weekly_timesheet,
    validate_attendance_for_log,
    manager_dashboard,
    missing_timesheets,
    reject_timesheet,
    submit_timesheet,
    week_bounds,
    is_current_week,
)
from .models import TimesheetConfig


def _user_perms(request) -> list:
    return getattr(request, "user_permissions", [])


@extend_schema(tags=["timesheets"])
class MyTimesheetWeekView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        week_start = request.query_params.get("week_start")
        anchor = date.fromisoformat(week_start) if week_start else date.today()
        sunday, saturday = week_bounds(anchor)
        weekly = get_or_create_weekly_timesheet(request.user, anchor)

        logs = WorkLog.objects.filter(
            employee=request.user,
            is_deleted=False,
            log_date__range=[sunday, saturday],
        ).select_related(
            "ticket__project", "ticket__parent", "weekly_timesheet",
        ).order_by("log_date", "created_at")

        loggable_dates = set(get_loggable_dates(request.user, sunday, saturday))
        current_week = is_current_week(anchor)
        week_editable = (
            current_week
            and weekly.status in (TimesheetStatus.DRAFT, TimesheetStatus.REJECTED)
        )
        days = []
        daily_cap = float(get_daily_capacity())
        for i in range(7):
            d = sunday + timedelta(days=i)
            day_logs = [l for l in logs if l.log_date == d]
            day_total = sum(float(l.hours) for l in day_logs)
            is_weekend = d.weekday() >= 5
            cap = 0.0 if is_weekend else daily_cap
            can_log = week_editable and d in loggable_dates
            att_hint = None
            if not current_week:
                att_hint = "Past weeks are view only — log time in the current week"
            elif not week_editable and weekly.status in (TimesheetStatus.SUBMITTED, TimesheetStatus.APPROVED):
                att_hint = f"Timesheet is {weekly.status.lower()} — view only"
            elif week_editable and d not in loggable_dates:
                att_hint = validate_attendance_for_log(request.user, d)
            days.append({
                "date": str(d),
                "day_name": d.strftime("%A"),
                "total_hours": round(day_total, 2),
                "capacity": cap,
                "over_capacity": cap > 0 and day_total > cap,
                "log_count": len(day_logs),
                "can_log": can_log,
                "attendance_hint": att_hint,
                "is_weekend": is_weekend,
            })

        payload = {
            "weekly_timesheet": WeeklyTimesheetSerializer(weekly).data,
            "days": days,
            "logs": WorkLogDetailSerializer(logs, many=True).data,
            "daily_capacity": get_daily_capacity(),
            "is_editable": week_editable,
            "is_current_week": current_week,
        }
        return Response(payload)


@extend_schema(tags=["timesheets"])
class MyTimesheetSubmitView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.submit"

    def post(self, request, timesheet_id):
        weekly = WeeklyTimesheet.objects.filter(
            id=timesheet_id,
            employee=request.user,
            is_deleted=False,
        ).first()
        if not weekly:
            week_start = request.data.get("week_start")
            if week_start:
                weekly = WeeklyTimesheet.objects.filter(
                    employee=request.user,
                    week_start=week_start,
                    is_deleted=False,
                ).first()
        if not weekly:
            return Response({"detail": "Timesheet not found."}, status=status.HTTP_404_NOT_FOUND)

        from rest_framework.exceptions import ValidationError as DRFValidationError
        from rest_framework import serializers as drf_serializers

        try:
            weekly = submit_timesheet(weekly, request.user)
        except drf_serializers.ValidationError as exc:
            raise DRFValidationError(detail=exc.detail)

        return Response(WeeklyTimesheetSerializer(weekly).data)


@extend_schema(tags=["timesheets"])
class MyTimesheetCopyDayView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.create"

    def post(self, request):
        ser = CopyDaySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        created = copy_logs_from_date(
            request.user,
            ser.validated_data["source_date"],
            ser.validated_data["target_date"],
        )
        return Response({
            "copied": len(created),
            "logs": WorkLogSerializer(created, many=True).data,
        })


@extend_schema(tags=["timesheets"])
class MyTimesheetCopyWeekView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.create"

    def post(self, request):
        ser = CopyWeekSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        count = copy_logs_from_week(
            request.user,
            ser.validated_data["source_week_start"],
            ser.validated_data["target_week_start"],
        )
        return Response({"copied": count})


@extend_schema(tags=["timesheets"])
class LoggableTicketsView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        log_date_str = request.query_params.get("log_date", str(date.today()))
        log_date = date.fromisoformat(log_date_str)
        search = request.query_params.get("search", "")
        att_err = validate_attendance_for_log(request.user, log_date)
        tickets, hints = get_loggable_tickets_with_hints(request.user, log_date, search)

        from .services import ticket_hierarchy
        data = []
        for t in tickets:
            hier = ticket_hierarchy(t)
            data.append({
                "id": t.id,
                "ticket_id": t.ticket_id,
                "title": t.title,
                "type": t.type,
                "project_id": t.project_id,
                "project_name": t.project.name,
                "epic_title": hier["epic_title"],
                "story_title": hier["story_title"],
            })
        return Response({
            "tickets": data,
            "hints": hints,
            "can_log": att_err is None,
            "attendance_hint": att_err,
        })


@extend_schema(tags=["timesheets"])
class LoggableDatesView(APIView):
    """Dates in a range where the employee may log time (attendance completed)."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        date_from = request.query_params.get("date_from")
        date_to = request.query_params.get("date_to")
        if not date_from or not date_to:
            return Response({"detail": "date_from and date_to are required."}, status=400)
        start = date.fromisoformat(date_from)
        end = date.fromisoformat(date_to)
        dates = get_loggable_dates(request.user, start, end)
        return Response({"dates": [str(d) for d in dates]})


# ── Legacy my-timesheet list (GET only) ───────────────────────────────────────

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
            "logs": WorkLogDetailSerializer(logs, many=True).data,
        })


# ── Manager / Reporting ───────────────────────────────────────────────────────

class ReportingDashboardView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def get(self, request):
        return Response(manager_dashboard(request.user))


class ReportingReviewView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def get(self, request):
        qs = WeeklyTimesheet.objects.filter(
            is_deleted=False,
            status=TimesheetStatus.SUBMITTED,
        ).select_related("employee")

        week_start = request.query_params.get("week_start")
        if week_start:
            qs = qs.filter(week_start=week_start)

        project_id = request.query_params.get("project")
        employee_id = request.query_params.get("employee")
        status_filter = request.query_params.get("status")

        if status_filter:
            qs = WeeklyTimesheet.objects.filter(is_deleted=False, status=status_filter)
            if week_start:
                qs = qs.filter(week_start=week_start)

        if employee_id:
            qs = qs.filter(employee_id=employee_id)

        perms = _user_perms(request)
        if not (request.user.is_staff or getattr(request.user, "is_superuser", False)):
            qs = [ts for ts in qs if can_review_timesheet(request.user, ts, perms)]

        if project_id:
            filtered = []
            for ts in qs:
                has_proj = WorkLog.objects.filter(
                    weekly_timesheet=ts, ticket__project_id=project_id, is_deleted=False,
                ).exists()
                if has_proj:
                    filtered.append(ts)
            qs = filtered

        data = []
        for ts in qs:
            row = WeeklyTimesheetSerializer(ts).data
            row["can_review"] = can_review_timesheet(request.user, ts, perms)
            data.append(row)
        return Response(data)


class ReportingApproveView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def post(self, request):
        ser = ReviewTimesheetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        weekly = WeeklyTimesheet.objects.filter(
            id=ser.validated_data["timesheet_id"], is_deleted=False,
        ).first()
        if not weekly:
            return Response({"detail": "Not found."}, status=404)
        weekly = approve_timesheet(
            weekly, request.user,
            ser.validated_data.get("comment", ""),
            _user_perms(request),
        )
        return Response(WeeklyTimesheetSerializer(weekly).data)


class ReportingRejectView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def post(self, request):
        ser = ReviewTimesheetSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        weekly = WeeklyTimesheet.objects.filter(
            id=ser.validated_data["timesheet_id"], is_deleted=False,
        ).first()
        if not weekly:
            return Response({"detail": "Not found."}, status=404)
        weekly = reject_timesheet(
            weekly, request.user,
            ser.validated_data.get("comment", ""),
            _user_perms(request),
        )
        return Response(WeeklyTimesheetSerializer(weekly).data)


class ReportingBulkApproveView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def post(self, request):
        ser = BulkReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        perms = _user_perms(request)
        approved = []
        for tid in ser.validated_data["timesheet_ids"]:
            weekly = WeeklyTimesheet.objects.filter(id=tid, is_deleted=False).first()
            if weekly:
                try:
                    approved.append(approve_timesheet(
                        weekly, request.user,
                        ser.validated_data.get("comment", ""),
                        perms,
                    ))
                except Exception:
                    pass
        return Response(WeeklyTimesheetSerializer(approved, many=True).data)


class ReportingBulkRejectView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def post(self, request):
        ser = BulkReviewSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        perms = _user_perms(request)
        rejected = []
        for tid in ser.validated_data["timesheet_ids"]:
            weekly = WeeklyTimesheet.objects.filter(id=tid, is_deleted=False).first()
            if weekly:
                try:
                    rejected.append(reject_timesheet(
                        weekly, request.user,
                        ser.validated_data.get("comment", ""),
                        perms,
                    ))
                except Exception:
                    pass
        return Response(WeeklyTimesheetSerializer(rejected, many=True).data)


class MissingTimesheetView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.approve"

    def get(self, request):
        return Response(missing_timesheets(request.user))


class UtilizationReportView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.utilization"

    def get(self, request):
        year = int(request.query_params.get("year", date.today().year))
        month = int(request.query_params.get("month", date.today().month))
        employee_id = request.query_params.get("employee")

        from apps.accounts.models import Employee
        if employee_id:
            employees = Employee.objects.filter(id=employee_id, is_deleted=False)
        elif request.user.is_staff:
            employees = Employee.objects.filter(is_active=True, is_deleted=False)
        else:
            employees = Employee.objects.filter(
                Q(manager=request.user) | Q(id=request.user.id),
                is_active=True, is_deleted=False,
            )
        return Response([
            CapacityService.employee_monthly_capacity(emp, year, month)
            for emp in employees
        ])


@extend_schema(tags=["timesheets"], responses={200: OpenApiResponse(description="Team timesheet utilization summary")})
class TeamTimesheetView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.utilization"

    def get(self, request):
        year = int(request.query_params.get("year", date.today().year))
        month = int(request.query_params.get("month", date.today().month))
        from apps.accounts.models import Employee
        employees = Employee.objects.filter(is_active=True, is_deleted=False)
        return Response([
            CapacityService.employee_monthly_capacity(emp, year, month)
            for emp in employees
        ])


class TimesheetConfigView(APIView):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.timesheet.view"

    def get(self, request):
        row = TimesheetConfig.objects.filter(is_deleted=False).first()
        if not row:
            row = TimesheetConfig.objects.create(daily_capacity_hours=8)
        return Response(TimesheetConfigSerializer(row).data)

    def patch(self, request):
        perms = _user_perms(request)
        if not (request.user.is_staff or "pmt.master.project.update" in perms):
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Admin permission required.")
        row = TimesheetConfig.objects.filter(is_deleted=False).first()
        if not row:
            row = TimesheetConfig.objects.create(daily_capacity_hours=8)
        ser = TimesheetConfigSerializer(row, data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        ser.save(updated_by=request.user)
        return Response(ser.data)
