from datetime import date, timedelta

from django.db.models import Sum, Count, Q, Avg
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Employee
from apps.allocation.models import Allocation
from apps.allocation.services import CapacityService
from apps.attendance.models import AttendanceRecord, AttendanceStatus, LeaveBalance, LeaveRequest, LeaveRequestStatus
from drf_spectacular.utils import extend_schema, OpenApiResponse
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.projects.models import Project
from apps.tickets.models import Ticket
from apps.workitems.models import WorkLog
from apps.payroll.models import Payroll
from apps.timesheets.models import WeeklyTimesheet
from apps.common.constants import TimesheetStatus
from apps.timesheets.services import missing_timesheets, week_bounds


def _project_health_status(project, today):
    """Return ON_TRACK | AT_RISK | DELAYED for a project."""
    if project.end_date and project.end_date < today:
        return "DELAYED"
    if not project.end_date:
        return "ON_TRACK"

    days_left = (project.end_date - today).days
    total_days = (project.end_date - project.start_date).days if project.start_date else None
    open_tickets = Ticket.objects.filter(
        project=project, is_deleted=False, workflow_state__is_final=False,
    ).count()
    total_tickets = Ticket.objects.filter(project=project, is_deleted=False).count()
    open_ratio = (open_tickets / total_tickets) if total_tickets else 0

    if total_days and days_left / total_days < 0.2 and open_ratio > 0.4:
        return "DELAYED"
    if (total_days and days_left / total_days < 0.35) or open_ratio > 0.6:
        return "AT_RISK"
    return "ON_TRACK"


def _portfolio_projects(projects_qs, today, year=None, month=None):
    """Build enriched project list + health summary."""
    on_track = at_risk = delayed = 0
    project_list = []

    for p in projects_qs.select_related("client", "manager"):
        health = _project_health_status(p, today)
        if health == "ON_TRACK":
            on_track += 1
        elif health == "AT_RISK":
            at_risk += 1
        else:
            delayed += 1

        total_tickets = Ticket.objects.filter(project=p, is_deleted=False).count()
        done_tickets = Ticket.objects.filter(
            project=p, is_deleted=False, workflow_state__is_final=True,
        ).count()
        completion_pct = round((done_tickets / total_tickets * 100), 1) if total_tickets else 0

        logged_hours = 0.0
        if year and month:
            logged_hours = float(
                WorkLog.objects.filter(
                    ticket__project=p, is_deleted=False,
                    log_date__year=year, log_date__month=month,
                ).aggregate(t=Sum("hours"))["t"] or 0
            )

        days_left = (p.end_date - today).days if p.end_date else None
        estimate = float(p.estimated_hours or 0)
        hours_pct = round((logged_hours / estimate * 100), 1) if estimate > 0 else 0

        project_list.append({
            "id": str(p.id),
            "name": p.name,
            "code": p.code,
            "client": p.client.name if p.client else None,
            "manager": p.manager.full_name if p.manager else None,
            "start_date": str(p.start_date) if p.start_date else None,
            "end_date": str(p.end_date) if p.end_date else None,
            "days_left": days_left,
            "health": health,
            "total_tickets": total_tickets,
            "open_tickets": total_tickets - done_tickets,
            "completion_pct": completion_pct,
            "estimated_hours": estimate,
            "logged_hours_month": round(logged_hours, 1),
            "hours_utilization_pct": hours_pct,
        })

    return {
        "summary": {"on_track": on_track, "at_risk": at_risk, "delayed": delayed},
        "projects": project_list,
    }


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="PMO dashboard KPIs")})
class PMODashboardView(APIView):
    """Central PMO dashboard — all key metrics in one response."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.dashboard.project.view"

    def get(self, request):
        today = date.today()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))

        active_projects_qs = Project.objects.filter(is_deleted=False, is_active=True)
        portfolio = _portfolio_projects(active_projects_qs, today, year, month)
        health_summary = portfolio["summary"]

        project_summary = {
            "total":    Project.objects.filter(is_deleted=False).count(),
            "active":   active_projects_qs.count(),
            "inactive": Project.objects.filter(is_deleted=False, is_active=False).count(),
            "on_track": health_summary["on_track"],
            "at_risk":  health_summary["at_risk"],
            "delayed":  health_summary["delayed"],
        }

        tickets_qs = Ticket.objects.filter(is_deleted=False)
        workitem_summary = {
            "open":        tickets_qs.filter(workflow_state__is_initial=True).count(),
            "in_progress": tickets_qs.filter(
                workflow_state__is_initial=False, workflow_state__is_final=False,
            ).count(),
            "done":  tickets_qs.filter(workflow_state__is_final=True).count(),
            "total": tickets_qs.count(),
        }
        overdue_count = tickets_qs.filter(
            due_date__lt=today, workflow_state__is_final=False,
        ).count()
        overdue_tickets = [
            {
                "id": str(t.id),
                "ticket_id": t.ticket_id,
                "title": t.title,
                "project_code": t.project.code if t.project else None,
                "project_name": t.project.name if t.project else None,
                "due_date": str(t.due_date),
                "days_overdue": (today - t.due_date).days,
            }
            for t in tickets_qs.filter(
                due_date__lt=today, workflow_state__is_final=False,
            ).select_related("project").order_by("due_date")[:25]
        ]

        ticket_by_type = list(
            tickets_qs.values("type").annotate(count=Count("id")).order_by("-count")
        )

        logs_this_month = WorkLog.objects.filter(
            is_deleted=False, log_date__year=year, log_date__month=month,
        )
        total_logged = float(logs_this_month.aggregate(t=Sum("hours"))["t"] or 0)
        billable_logged = float(
            logs_this_month.filter(is_billable=True).aggregate(t=Sum("hours"))["t"] or 0
        )
        billing_util_pct = (billable_logged / total_logged * 100) if total_logged > 0 else 0

        hours_by_project = [
            {
                "project_id": str(row["ticket__project_id"]),
                "name": row["ticket__project__name"],
                "code": row["ticket__project__code"],
                "hours": round(float(row["hours"] or 0), 1),
            }
            for row in logs_this_month.filter(ticket__isnull=False)
            .values("ticket__project_id", "ticket__project__name", "ticket__project__code")
            .annotate(hours=Sum("hours"))
            .order_by("-hours")[:8]
        ]

        week_sunday, _ = week_bounds()
        weekly_trend = []
        for i in range(7, -1, -1):
            ws = week_sunday - timedelta(weeks=i)
            we = ws + timedelta(days=6)
            wq = WorkLog.objects.filter(is_deleted=False, log_date__range=[ws, we])
            w_total = float(wq.aggregate(t=Sum("hours"))["t"] or 0)
            w_bill = float(wq.filter(is_billable=True).aggregate(t=Sum("hours"))["t"] or 0)
            weekly_trend.append({
                "week_start": str(ws),
                "label": ws.strftime("%d %b"),
                "total_hours": round(w_total, 1),
                "billable_hours": round(w_bill, 1),
            })

        active_employees = Employee.objects.filter(is_active=True, is_deleted=False)
        over_allocated = []
        util_pcts = []
        for emp in active_employees:
            cap = CapacityService.employee_monthly_capacity(emp, year, month)
            util_pcts.append(cap["utilization_percent"])
            if cap["is_over_allocated"]:
                over_allocated.append({"name": emp.full_name, "id": str(emp.id)})

        avg_utilization = round(sum(util_pcts) / len(util_pcts), 1) if util_pcts else 0

        week_sunday, _ = week_bounds()
        missing_ts = missing_timesheets()
        timesheet_week = {
            "week_start": str(week_sunday),
            "draft": WeeklyTimesheet.objects.filter(
                week_start=week_sunday, status=TimesheetStatus.DRAFT, is_deleted=False,
            ).count(),
            "submitted": WeeklyTimesheet.objects.filter(
                week_start=week_sunday, status=TimesheetStatus.SUBMITTED, is_deleted=False,
            ).count(),
            "approved": WeeklyTimesheet.objects.filter(
                week_start=week_sunday, status=TimesheetStatus.APPROVED, is_deleted=False,
            ).count(),
            "rejected": WeeklyTimesheet.objects.filter(
                week_start=week_sunday, status=TimesheetStatus.REJECTED, is_deleted=False,
            ).count(),
            "missing": len(missing_ts),
            "missing_details": missing_ts,
        }

        alerts = []
        if overdue_count:
            alerts.append({
                "key": "overdue_tickets",
                "severity": "error", "title": "Overdue tickets",
                "count": overdue_count, "path": "/tickets",
                "detail": "Tickets past due date still open",
            })
        if health_summary["delayed"]:
            alerts.append({
                "key": "delayed_projects",
                "severity": "error", "title": "Delayed projects",
                "count": health_summary["delayed"], "path": "/projects",
                "detail": "Projects past end date or critical path risk",
            })
        if health_summary["at_risk"]:
            alerts.append({
                "key": "at_risk_projects",
                "severity": "warning", "title": "At-risk projects",
                "count": health_summary["at_risk"], "path": "/projects",
                "detail": "Timeline or completion rate needs attention",
            })
        if over_allocated:
            alerts.append({
                "key": "over_allocated",
                "severity": "warning", "title": "Over-allocated staff",
                "count": len(over_allocated), "path": "/allocation",
                "detail": "Resource allocation exceeds 100%",
            })
        if timesheet_week["missing"]:
            alerts.append({
                "key": "missing_timesheets",
                "severity": "warning", "title": "Missing timesheets",
                "count": timesheet_week["missing"], "path": "/timesheets/reporting",
                "detail": "Allocated employees without submitted timesheet",
            })

        return Response({
            "date": str(today),
            "period": {"year": year, "month": month},
            "projects": project_summary,
            "portfolio": portfolio,
            "work_items": {**workitem_summary, "overdue": overdue_count, "overdue_tickets": overdue_tickets},
            "ticket_by_type": ticket_by_type,
            "logging": {
                "total_hours": round(total_logged, 1),
                "billable_hours": round(billable_logged, 1),
                "non_billable_hours": round(total_logged - billable_logged, 1),
                "billing_utilization_percent": round(billing_util_pct, 1),
                "hours_by_project": hours_by_project,
                "weekly_trend": weekly_trend,
            },
            "team": {
                "total_active": active_employees.count(),
                "over_allocated": over_allocated,
                "over_allocated_count": len(over_allocated),
                "avg_utilization_percent": avg_utilization,
            },
            "timesheet_week": timesheet_week,
            "alerts": alerts,
        })


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="Resource utilization heatmap")})
class UtilizationHeatmapView(APIView):
    """Resource utilization heatmap — employee vs project matrix."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.project.report.utilization"

    def get(self, request):
        year = int(request.query_params.get("year", date.today().year))
        month = int(request.query_params.get("month", date.today().month))

        employees = Employee.objects.filter(is_active=True, is_deleted=False)
        matrix = []
        for emp in employees:
            cap = CapacityService.employee_monthly_capacity(emp, year, month)
            # Per-project breakdown
            allocs = Allocation.objects.filter(
                employee=emp, is_deleted=False
            ).select_related("project")
            projects_breakdown = [
                {
                    "project_id": str(a.project.id),
                    "project_name": a.project.name,
                    "allocation_pct": float(a.allocation_percentage),
                    "daily_hours": a.daily_hours,
                }
                for a in allocs
            ]
            matrix.append({**cap, "projects": projects_breakdown})
        return Response(matrix)


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="Employee self-service dashboard")})
class EmployeeDashboardView(APIView):
    """Personal dashboard — scoped to request.user; requires pmt.dashboard.own.view."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.dashboard.own.view"

    def get(self, request):
        me = request.user
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        month_start = today.replace(day=1)

        # ── Profile ──────────────────────────────────────────────────
        desig_name = ""
        dept_name = ""
        try:
            desig_name = me.designation_ref.name if me.designation_ref_id else (me.designation or "")
            dept_name  = me.department_ref.name  if me.department_ref_id  else (me.department  or "")
        except Exception:
            pass

        profile_pic_url = None
        try:
            profile_pic_url = me.profile_picture.url if me.profile_picture else None
        except Exception:
            pass

        profile = {
            "id":                  str(me.id),
            "full_name":           me.full_name,
            "employee_code":       me.employee_code,
            "email":               me.email,
            "designation":         desig_name,
            "department":          dept_name,
            "grade":               me.grade.name if me.grade_id else "",
            "keycloak_group":      me.keycloak_group,
            "joining_date":        str(me.joining_date) if me.joining_date else None,
            "profile_picture_url": profile_pic_url,
            "shift_applicable":    bool(me.shift_applicable),
        }

        # ── Tickets ───────────────────────────────────────────────────
        my_items = Ticket.objects.filter(assignee=me, is_deleted=False)
        work_items = {
            "open":        my_items.filter(workflow_state__is_initial=True).count(),
            "in_progress": my_items.filter(workflow_state__is_initial=False, workflow_state__is_final=False).count(),
            "in_review":   0,
            "done":        my_items.filter(workflow_state__is_final=True).count(),
            "total":       my_items.count(),
            "overdue":     my_items.filter(
                due_date__lt=today,
                workflow_state__is_final=False,
            ).count(),
        }

        # ── Recent open/in-progress tickets ──────────────────────────
        recent_items = my_items.filter(
            workflow_state__is_final=False
        ).select_related("project", "workflow_state").order_by("due_date")[:8]
        recent_items_data = [
            {
                "id":           str(t.id),
                "ticket_number": t.ticket_id,
                "title":        t.title,
                "type":         t.type,
                "status":       t.workflow_state.name if t.workflow_state else "",
                "priority":     t.priority,
                "due_date":     str(t.due_date) if t.due_date else None,
                "project":      t.project.name,
            }
            for t in recent_items
        ]

        # ── Pending follow-ups (assigned to me) ───────────────────────
        pending_followups_data = []
        user_perms = getattr(request, "user_permissions", [])
        if "pmt.crm.followup.view" in user_perms or request.user.is_superuser:
            from apps.followups.models import FollowUp
            from django.db.models import Case, When, IntegerField, Value

            priority_order = Case(
                When(priority="IMPORTANT", then=Value(0)),
                When(priority="HIGH", then=Value(1)),
                When(priority="MEDIUM", then=Value(2)),
                When(priority="LOW", then=Value(3)),
                default=Value(4),
                output_field=IntegerField(),
            )
            visible = Q(assignee_id=me.pk) | Q(reporter_id=me.pk)
            pending_base = FollowUp.objects.filter(
                is_deleted=False,
                workflow_state__is_final=False,
            )
            if "pmt.crm.followup.view_all" in user_perms:
                pending_qs = pending_base
            else:
                pending_qs = pending_base.filter(visible)
            pending_qs = pending_qs.select_related("workflow_state").annotate(
                priority_rank=priority_order,
            ).order_by("priority_rank", "due_date", "start_time")[:10]
            pending_followups_data = [
                {
                    "id":                  str(f.id),
                    "title":               f.title,
                    "type":                f.type,
                    "type_label":          f.get_type_display(),
                    "priority":            f.priority,
                    "priority_label":      f.get_priority_display(),
                    "description":         f.description,
                    "due_date":            str(f.due_date) if f.due_date else None,
                    "start_time":          f.start_time.strftime("%H:%M") if f.start_time else None,
                    "end_time":            f.end_time.strftime("%H:%M") if f.end_time else None,
                    "is_overdue":          bool(f.due_date and f.due_date < today),
                    "assignee_name":       f.assignee.full_name if f.assignee else "",
                    "workflow_state_slug": f.workflow_state.slug if f.workflow_state else "",
                    "workflow_state_name": f.workflow_state.name if f.workflow_state else "",
                }
                for f in pending_qs
            ]

        # ── My active project allocations ─────────────────────────────
        allocations = Allocation.objects.filter(
            employee=me, is_deleted=False,
        ).filter(
            Q(end_date__gte=today) | Q(end_date__isnull=True)
        ).select_related("project", "project__client").order_by("-allocation_percentage")[:6]

        my_projects = [
            {
                "id":                    str(a.project.id),
                "name":                  a.project.name,
                "code":                  a.project.code,
                "client":                a.project.client.name if a.project.client_id else "",
                "is_active":             a.project.is_active,
                "allocation_percentage": float(a.allocation_percentage),
                "start_date":            str(a.start_date),
                "end_date":              str(a.end_date) if a.end_date else None,
            }
            for a in allocations
        ]

        # ── Timesheet — this week ─────────────────────────────────────
        week_logs = WorkLog.objects.filter(
            employee=me, is_deleted=False, log_date__range=[start_of_week, today]
        )
        weekly_hours = float(week_logs.aggregate(t=Sum("hours"))["t"] or 0)

        # Daily breakdown for current month (for the mini chart)
        daily_logs = list(
            WorkLog.objects.filter(
                employee=me, is_deleted=False, log_date__range=[month_start, today]
            )
            .values("log_date")
            .annotate(hours=Sum("hours"))
            .order_by("log_date")
        )
        for d in daily_logs:
            d["log_date"] = str(d["log_date"])
            d["hours"] = float(d["hours"])

        # ── Recent work logs (current calendar week only) ─────────────
        week_start, week_end = week_bounds(today)
        recent_logs = WorkLog.objects.filter(
            employee=me,
            is_deleted=False,
            log_date__range=[week_start, week_end],
        ).select_related("ticket__project").order_by("-log_date")
        recent_logs_data = [
            {
                "id":         str(wl.id),
                "log_date":   str(wl.log_date),
                "hours":      float(wl.hours),
                "notes":      wl.remarks or "",
                "work_item":  wl.ticket.title if wl.ticket_id else "",
                "ticket":     wl.ticket.ticket_id if wl.ticket_id else "",
                "project":    wl.ticket.project.name if wl.ticket_id else "",
                "is_billable": wl.is_billable,
            }
            for wl in recent_logs
        ]

        # ── Attendance — today ────────────────────────────────────────
        from apps.attendance.models import AttendanceBreak
        today_attendance = AttendanceRecord.objects.filter(
            employee=me, date=today, is_deleted=False
        ).prefetch_related("breaks").first()
        if today_attendance:
            import datetime as dt
            ci = today_attendance.check_in
            co = today_attendance.check_out
            duration = 0.0
            if ci and co:
                a = dt.datetime.combine(today, ci)
                b = dt.datetime.combine(today, co)
                if b > a:
                    duration = round((b - a).seconds / 3600, 2)
            breaks_data = [
                {
                    "id":               str(b.id),
                    "break_type":       b.break_type,
                    "break_type_label": b.get_break_type_display(),
                    "start_time":       b.start_time.strftime("%H:%M"),
                    "end_time":         b.end_time.strftime("%H:%M") if b.end_time else None,
                    "duration_minutes": b.duration_minutes,
                }
                for b in today_attendance.breaks.filter(is_deleted=False).order_by("start_time")
            ]
            attendance_today = {
                "status":               today_attendance.status,
                "check_in":             ci.strftime("%H:%M") if ci else None,
                "check_out":            co.strftime("%H:%M") if co else None,
                "duration_hours":       duration,
                "working_hours":        today_attendance.working_hours,
                "total_break_minutes":  today_attendance.total_break_minutes,
                "breaks":               breaks_data,
            }
        else:
            attendance_today = {
                "status": None, "check_in": None, "check_out": None,
                "duration_hours": 0, "working_hours": 0, "total_break_minutes": 0, "breaks": [],
            }

        # ── Attendance — this month ───────────────────────────────────
        month_records = AttendanceRecord.objects.filter(
            employee=me, date__year=today.year, date__month=today.month, is_deleted=False
        )
        attendance_month = {
            "present":  month_records.filter(status=AttendanceStatus.PRESENT).count(),
            "wfh":      month_records.filter(status=AttendanceStatus.WFH).count(),
            "half_day": month_records.filter(status=AttendanceStatus.HALF_DAY).count(),
            "on_leave": month_records.filter(status=AttendanceStatus.ON_LEAVE).count(),
        }

        # ── Leave Balances ────────────────────────────────────────────
        leave_balances = []
        for lb in LeaveBalance.objects.filter(
            employee=me, year=today.year
        ).select_related("leave_type"):
            leave_balances.append({
                "leave_type":  lb.leave_type.name,
                "code":        lb.leave_type.code,
                "color":       lb.leave_type.color,
                "is_paid":     lb.leave_type.is_paid,
                "total":       float(lb.total_days),
                "used":        float(lb.used_days),
                "remaining":   lb.remaining_days,
            })

        # ── Work & break statistics — this month ─────────────────────
        import datetime as _dt
        working_recs = list(month_records.filter(
            status__in=[AttendanceStatus.PRESENT, AttendanceStatus.WFH, AttendanceStatus.HALF_DAY]
        ).prefetch_related("breaks"))
        working_days_count = len(working_recs)
        total_work_hours   = sum(r.working_hours for r in working_recs)
        total_break_mins   = sum(r.total_break_minutes for r in working_recs)

        shift_start_time = None
        try:
            if me.shift_category_id:
                shift_start_time = me.shift_category.start_time
            elif me.custom_shift_start:
                shift_start_time = me.custom_shift_start
        except Exception:
            pass

        # On-time stats (only if shift is configured)
        on_time = late = early = 0
        if shift_start_time:
            import datetime as _dt2
            late_threshold  = (_dt2.datetime.combine(_dt2.date.today(), shift_start_time)
                               + _dt2.timedelta(minutes=5)).time()
            early_threshold = (_dt2.datetime.combine(_dt2.date.today(), shift_start_time)
                               - _dt2.timedelta(minutes=5)).time()
            for rec in working_recs:
                if rec.check_in:
                    if rec.check_in <= early_threshold:
                        early += 1
                    elif rec.check_in <= late_threshold:
                        on_time += 1
                    else:
                        late += 1

        # ── Recent leave requests ─────────────────────────────────────
        recent_leaves = LeaveRequest.objects.filter(
            employee=me, is_deleted=False
        ).select_related("leave_type").order_by("-created_at")[:5]
        leave_requests_data = [
            {
                "id":         str(lr.id),
                "leave_type": lr.leave_type.name,
                "color":      lr.leave_type.color,
                "start_date": str(lr.start_date),
                "end_date":   str(lr.end_date),
                "days_count": float(lr.days_count),
                "status":     lr.status,
                "reason":     lr.reason,
            }
            for lr in recent_leaves
        ]

        # ── Reporting hierarchy ───────────────────────────────────────
        def _pic(emp):
            try:
                return emp.profile_picture.url if emp.profile_picture else None
            except Exception:
                return None

        def _node(emp, extra=None):
            desig = emp.designation_ref.name if emp.designation_ref_id else (emp.designation or "")
            dept  = emp.department_ref.name  if emp.department_ref_id  else (emp.department  or "")
            d = {
                "id":            str(emp.id),
                "name":          emp.full_name,
                "employee_code": emp.employee_code,
                "designation":   desig,
                "department":    dept,
                "avatar":        _pic(emp),
            }
            if extra:
                d.update(extra)
            return d

        def _count_all_reports(manager_id, all_emp_ids_by_manager):
            """Recursively count descendants using a pre-built map."""
            directs = all_emp_ids_by_manager.get(manager_id, [])
            return sum(1 + _count_all_reports(uid, all_emp_ids_by_manager) for uid in directs)

        # Build manager→children map once
        emp_manager_map: dict[str, list[str]] = {}
        for e in Employee.objects.filter(is_active=True, is_deleted=False).values("id", "manager_id"):
            if e["manager_id"]:
                key = str(e["manager_id"])
                emp_manager_map.setdefault(key, []).append(str(e["id"]))

        # Manager node
        manager_node = None
        if me.manager_id:
            try:
                mgr = Employee.objects.select_related(
                    "designation_ref", "department_ref"
                ).get(pk=me.manager_id, is_active=True, is_deleted=False)
                manager_node = _node(mgr)
            except Employee.DoesNotExist:
                pass

        # Direct reports
        direct_reports_qs = Employee.objects.filter(
            manager=me, is_active=True, is_deleted=False
        ).select_related("designation_ref", "department_ref").order_by("first_name", "last_name")
        direct_reports_data = [
            _node(dr, {"report_count": _count_all_reports(str(dr.id), emp_manager_map)})
            for dr in direct_reports_qs
        ]

        total_team = _count_all_reports(str(me.id), emp_manager_map)

        reporting_hierarchy = {
            "manager":        manager_node,
            "direct_reports": direct_reports_data,
            "total_team":     total_team,
        }

        # ── Payslips — current financial year ────────────────────────
        # Financial year: Apr of current/prev year → Mar of next year
        fy_start_year = today.year if today.month >= 4 else today.year - 1
        fy_start = date(fy_start_year, 4, 1)
        fy_end   = date(fy_start_year + 1, 3, 31)
        payslips_qs = Payroll.objects.filter(
            employee=me, is_deleted=False,
        ).filter(
            Q(year=fy_start_year, month__gte=4) | Q(year=fy_start_year + 1, month__lte=3)
        ).order_by("-year", "-month")
        payslips_data = [
            {
                "id":         str(p.id),
                "month":      p.month,
                "month_name": p.month_name,
                "year":       p.year,
                "status":     p.status,
                "net_salary": float(p.net_salary),
            }
            for p in payslips_qs
        ]

        return Response({
            "profile":      profile,
            "work_items":   work_items,
            "recent_items": recent_items_data,
            "pending_followups": pending_followups_data,
            "my_projects":  my_projects,
            "timesheet": {
                "weekly_hours":    weekly_hours,
                "expected_hours":  40,
                "daily_logs":      daily_logs,
            },
            "recent_logs":       recent_logs_data,
            "attendance_today":  attendance_today,
            "attendance_month":  attendance_month,
            "checkin_stats": {
                "avg_working_hours": round(total_work_hours / max(working_days_count, 1), 2),
                "avg_break_minutes": round(total_break_mins  / max(working_days_count, 1), 1),
                "total_working_hours": round(total_work_hours, 2),
                "total_break_minutes": total_break_mins,
                "working_days_count":  working_days_count,
                "on_time":   on_time,
                "late":      late,
                "early":     early,
            },
            "leave_balances":    leave_balances,
            "leave_requests":    leave_requests_data,
            "payslips":             payslips_data,
            "payslips_fy":          f"FY {fy_start_year}-{str(fy_start_year + 1)[-2:]}",
            "reporting_hierarchy":  reporting_hierarchy,
        })


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="Project health summary")})
class ProjectHealthView(APIView):
    """
    Returns on-track / at-risk / delayed counts and per-project health signals
    based on due dates and ticket completion rate.
    """
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.dashboard.project.view"

    def get(self, request):
        today = date.today()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
        projects = Project.objects.filter(is_deleted=False, is_active=True)
        portfolio = _portfolio_projects(projects, today, year, month)
        return Response(portfolio)


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="HRMS dashboard KPIs")})
class HRMSDashboardView(APIView):
    """HRMS dashboard — headcount, attendance, leave and payroll KPIs."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.dashboard.hrms.view"

    def get(self, request):
        from apps.master.models import Department
        from apps.payroll.models import Payroll, PayrollStatus

        today = date.today()
        month_start = today.replace(day=1)
        last_30 = today - timedelta(days=30)

        # ── Headcount ────────────────────────────────────────────────
        emp_qs = Employee.objects.filter(is_active=True, is_deleted=False)
        total_active = emp_qs.count()

        # New joiners this month
        new_joiners_count = emp_qs.filter(joining_date__gte=month_start).count()

        # By department
        dept_dist = list(
            emp_qs.values("department_ref__name")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        dept_distribution = [
            {"department": d["department_ref__name"] or "Unassigned", "count": d["count"]}
            for d in dept_dist
        ]

        # By keycloak group (role distribution)
        group_dist = list(
            emp_qs.values("keycloak_group")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        role_distribution = [
            {"role": g["keycloak_group"] or "Unassigned", "count": g["count"]}
            for g in group_dist
        ]

        # ── Today's attendance ────────────────────────────────────────
        today_records = AttendanceRecord.objects.filter(date=today, is_deleted=False)
        att_counts = {s: 0 for s in ["PRESENT", "WFH", "HALF_DAY", "ON_LEAVE", "ABSENT"]}
        for rec in today_records.values("status").annotate(n=Count("id")):
            if rec["status"] in att_counts:
                att_counts[rec["status"]] = rec["n"]
        marked_today = today_records.count()
        not_marked_today = max(0, total_active - marked_today)
        attendance_rate = round(
            ((att_counts["PRESENT"] + att_counts["WFH"]) / total_active * 100) if total_active else 0, 1
        )

        # ── Leave requests ────────────────────────────────────────────
        lr_qs = LeaveRequest.objects.filter(is_deleted=False)
        pending_leave_count = lr_qs.filter(status=LeaveRequestStatus.PENDING).count()

        # Pending leave requests detail (latest 10)
        pending_leaves = lr_qs.filter(
            status=LeaveRequestStatus.PENDING
        ).select_related("employee", "leave_type").order_by("start_date")[:10]
        pending_leave_list = [
            {
                "id":           str(lr.id),
                "employee":     lr.employee.full_name,
                "employee_code": lr.employee.employee_code,
                "leave_type":   lr.leave_type.name,
                "color":        lr.leave_type.color,
                "start_date":   str(lr.start_date),
                "end_date":     str(lr.end_date),
                "days_count":   float(lr.days_count),
                "reason":       lr.reason or "",
            }
            for lr in pending_leaves
        ]

        # Leave status distribution this month
        leave_this_month = lr_qs.filter(created_at__date__gte=month_start)
        leave_stats = {
            "pending":  leave_this_month.filter(status=LeaveRequestStatus.PENDING).count(),
            "approved": leave_this_month.filter(status=LeaveRequestStatus.APPROVED).count(),
            "rejected": leave_this_month.filter(status=LeaveRequestStatus.REJECTED).count(),
        }

        # ── Recent joiners (last 30 days) ─────────────────────────────
        recent_joiners_qs = emp_qs.filter(
            joining_date__gte=last_30
        ).select_related("designation_ref", "department_ref").order_by("-joining_date")[:8]
        recent_joiners = [
            {
                "id":           str(e.id),
                "full_name":    e.full_name,
                "employee_code": e.employee_code,
                "designation":  e.designation_ref.name if e.designation_ref_id else (e.designation or ""),
                "department":   e.department_ref.name  if e.department_ref_id  else (e.department  or ""),
                "joining_date": str(e.joining_date),
            }
            for e in recent_joiners_qs
        ]

        # ── Payroll — current month ───────────────────────────────────
        payroll_this_month = Payroll.objects.filter(
            month=today.month, year=today.year, is_deleted=False
        )
        payroll_stats = {
            "total":     payroll_this_month.count(),
            "draft":     payroll_this_month.filter(status=PayrollStatus.DRAFT).count(),
            "finalized": payroll_this_month.filter(status=PayrollStatus.FINALIZED).count(),
            "paid":      payroll_this_month.filter(status=PayrollStatus.PAID).count(),
        }

        return Response({
            "date": str(today),
            "headcount": {
                "total_active":      total_active,
                "new_joiners_month": new_joiners_count,
                "dept_distribution": dept_distribution,
                "role_distribution": role_distribution,
            },
            "attendance_today": {
                **att_counts,
                "not_marked":       not_marked_today,
                "attendance_rate":  attendance_rate,
            },
            "leave": {
                "pending_count":  pending_leave_count,
                "stats_this_month": leave_stats,
                "pending_list":   pending_leave_list,
            },
            "recent_joiners": recent_joiners,
            "payroll": payroll_stats,
        })


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="Executive dashboard")})
class ExecutiveDashboardView(APIView):
    """Cross-module executive dashboard for a financial year (Apr–Mar)."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.dashboard.executive.view"

    def get(self, request):
        from .executive_service import build_executive_dashboard
        from .fy_utils import current_fy_start

        today = date.today()
        try:
            fy_start_year = int(request.query_params.get("fy_start_year", current_fy_start(today)))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid fy_start_year."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            data = build_executive_dashboard(fy_start_year, today)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)


@extend_schema(tags=["dashboard"], responses={200: OpenApiResponse(description="Executive project detail")})
class ExecutiveProjectDetailView(APIView):
    """Project financial drill-down for executive dashboard popup."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.dashboard.executive.view"

    def get(self, request, project_id):
        from .executive_service import build_project_executive_detail
        from .fy_utils import current_fy_start

        today = date.today()
        try:
            fy_start_year = int(request.query_params.get("fy_start_year", current_fy_start(today)))
        except (TypeError, ValueError):
            return Response(
                {"detail": "Invalid fy_start_year."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            data = build_project_executive_detail(project_id, fy_start_year, today)
        except Project.DoesNotExist:
            return Response({"detail": "Project not found."}, status=status.HTTP_404_NOT_FOUND)
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data)
