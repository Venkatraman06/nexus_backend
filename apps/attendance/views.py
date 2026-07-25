import calendar
import csv
import io
import datetime as dt
from datetime import date,timedelta

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from rest_framework import request, status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.allocation import models
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.accounts import models as account_models
from drf_spectacular.utils import extend_schema, OpenApiResponse

from packages.keycloak import permissions

from .models import (
    AttendanceRecord, AttendanceBreak, AttendanceStatus, BreakType,
    LeaveBalance, LeaveRequest, LeaveRequestStatus,
    AttendanceClockInEnable, ShiftChangeRequest, WFHRequest, WFHSetting,
)
from apps.master.models import LeaveType
from .serializers import (
    AttendanceRecordSerializer, CheckInSerializer, CheckOutSerializer,
    StartBreakSerializer,
    LeaveBalanceSerializer, LeaveRequestSerializer, LeaveReviewSerializer, LeaveTypeSerializer,
    AttendanceClockInEnableSerializer,
)
from apps.master.models import Holiday 
# ── Break time limits (minutes) ──────────────────────────────────────────────
BREAK_MAX_MINUTES = {
    "LUNCH": 45,
    "TEA":   20,
    "OTHER":  5,
}

# ── Short codes for CSV export ────────────────────────────────────────────────
STATUS_CODE = {
    "PRESENT":  "P",
    "WFH":      "WFH",
    "HALF_DAY": "HD",
    "ON_LEAVE": "OL",
    "HOLIDAY":  "HOL",
    "WEEKEND":  "—",
    "ABSENT":   "ABS",
}

STATUS_COLOR_MAP = {
    "PRESENT":  "#22c55e",
    "ABSENT":   "#ef4444",
    "WFH":      "#3b82f6",
    "HALF_DAY": "#f59e0b",
    "ON_LEAVE": "#7c3aed",
    "HOLIDAY":  "#0d9488",
    "WEEKEND":  "#d1d5db",
}


# ── Shift window helpers ──────────────────────────────────────────────────────

def _shift_times(employee):
    """Return (start_time, end_time) for the employee's shift, or (None, None)."""
    try:
        from .models import EmployeeShift
        es = EmployeeShift.objects.filter(
            employee=employee, is_deleted=False, effective_from__lte=date.today()
        ).filter(
            Q(effective_to__isnull=True) | Q(effective_to__gte=date.today())
        ).select_related("shift").order_by("-effective_from").first()
        if es:
            return es.shift.start_time, es.shift.end_time
        if employee.shift_category_id:
            sc = employee.shift_category
            return sc.start_time, sc.end_time
        if employee.custom_shift_start and employee.custom_shift_end:
            return employee.custom_shift_start, employee.custom_shift_end
    except Exception:
        pass
    return None, None


def _check_shift_window(now_time, shift_time, before_min: int, after_min: int):
    """
    Returns (ok: bool, message: str).
    Checks whether now_time falls within [shift_time - before_min, shift_time + after_min].
    """
    base = dt.datetime(2000, 1, 1)
    window_start = (base + dt.timedelta(
        hours=shift_time.hour, minutes=shift_time.minute
    ) - dt.timedelta(minutes=before_min)).time()
    window_end = (base + dt.timedelta(
        hours=shift_time.hour, minutes=shift_time.minute
    ) + dt.timedelta(minutes=after_min)).time()
    ok = window_start <= now_time <= window_end
    return ok, f"{window_start.strftime('%I:%M %p')} – {window_end.strftime('%I:%M %p')}"


def _is_shift_employee(employee) -> bool:
    """Only employees flagged shift_applicable use mapped shift time windows."""
    return bool(getattr(employee, "shift_applicable", False))


def get_clock_permissions(employee, *, on_date: date | None = None, at_time=None) -> dict:
    """Clock-in/out eligibility for dashboard and self-service UI."""
    today = on_date or date.today()
    now_time = at_time or dt.datetime.now().time()
    shift_start, shift_end = _shift_times(employee)
    hr_enabled = is_clockin_allowed_for_no_shift(employee, today)

    perms = {
        "shift_applicable": _is_shift_employee(employee),
        "shift_start": shift_start.strftime("%H:%M") if shift_start else None,
        "shift_end": shift_end.strftime("%H:%M") if shift_end else None,
        "clockin_enabled": hr_enabled,
        "can_clock_in": True,
        "can_clock_out": True,
        "clock_in_window": None,
        "clock_out_window": None,
    }

    if not _is_shift_employee(employee):
        return perms

    if hr_enabled:
        return perms

    if shift_start:
        ok, window = _check_shift_window(now_time, shift_start, 5, 5)
        perms["can_clock_in"] = ok
        perms["clock_in_window"] = window
    else:
        perms["can_clock_in"] = False

    if shift_end:
        ok, window = _check_shift_window(now_time, shift_end, 5, 10)
        perms["can_clock_out"] = ok
        perms["clock_out_window"] = window
    else:
        perms["can_clock_out"] = False

    return perms


# ── Self-service views ────────────────────────────────────────────────────────

class TodayAttendanceView(APIView):
    """Get today's attendance record for the current user."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"], responses={200: AttendanceRecordSerializer})
    def get(self, request):
        record = AttendanceRecord.objects.filter(
            employee=request.user, date=date.today(), is_deleted=False
        ).prefetch_related("breaks").first()
        if not record:
            return Response(None)
        return Response(AttendanceRecordSerializer(record).data)


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        today    = date.today()
        now_time = dt.datetime.now().time()
        lat      = serializer.validated_data.get("lat")
        lng      = serializer.validated_data.get("lng")
        me       = request.user

        # Shift employees: restrict check-in to mapped shift start window (HR override exempts).
        # Non-shift employees: may check in any time.
        if _is_shift_employee(me):
            hr_enabled = is_clockin_allowed_for_no_shift(me, today)
            if not hr_enabled:
                shift_start, _ = _shift_times(me)
                if shift_start:
                    ok, window = _check_shift_window(now_time, shift_start, before_min=5, after_min=5)
                    if not ok:
                        return Response(
                            {
                                "detail": (
                                    f"Check-in allowed only within 5 min of shift start "
                                    f"({shift_start.strftime('%I:%M %p')}). "
                                    f"Allowed window: {window}."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    return Response(
                        {"detail": "Shift timing is not configured for your profile."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # ... rest of your code unchanged
        record, created = AttendanceRecord.objects.get_or_create(
            employee=request.user, date=today,
            defaults={
                "check_in":     now_time,
                "check_in_lat": lat,
                "check_in_lng": lng,
                "status":       serializer.validated_data.get("status", AttendanceStatus.PRESENT),
                "notes":        serializer.validated_data.get("notes", ""),
            },
        )
        if not created:
            if record.check_in:
                return Response({"detail": "Already checked in today."}, status=status.HTTP_400_BAD_REQUEST)
            record.check_in     = now_time
            record.check_in_lat = lat
            record.check_in_lng = lng
            record.status       = serializer.validated_data.get("status", AttendanceStatus.PRESENT)
            record.notes        = serializer.validated_data.get("notes", "")
            record.save(update_fields=["check_in", "check_in_lat", "check_in_lng", "status", "notes"])

        return Response(AttendanceRecordSerializer(record).data)

class CheckOutView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CheckOutSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        now_time = dt.datetime.now().time()
        lat      = serializer.validated_data.get("lat")
        lng      = serializer.validated_data.get("lng")
        me       = request.user

        record = AttendanceRecord.objects.filter(
            employee=me, date=date.today(), is_deleted=False
        ).first()

        if not record:
            return Response({"detail": "No check-in found for today."}, status=status.HTTP_400_BAD_REQUEST)
        if record.check_out:
            return Response({"detail": "Already checked out today."}, status=status.HTTP_400_BAD_REQUEST)

        if _is_shift_employee(me):
            hr_enabled = is_clockin_allowed_for_no_shift(me, date.today())
            if not hr_enabled:
                _, shift_end = _shift_times(me)
                if shift_end:
                    ok, window = _check_shift_window(now_time, shift_end, before_min=5, after_min=10)
                    if not ok:
                        return Response(
                            {
                                "detail": (
                                    f"Check-out allowed only within 5 min before / 10 min after "
                                    f"shift end ({shift_end.strftime('%I:%M %p')}). "
                                    f"Allowed window: {window}."
                                )
                            },
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    return Response(
                        {"detail": "Shift timing is not configured for your profile."},
                        status=status.HTTP_403_FORBIDDEN,
                    )

        # Auto-close any open break
        AttendanceBreak.objects.filter(
            attendance=record, end_time__isnull=True, is_deleted=False
        ).update(end_time=now_time)

        record.check_out     = now_time
        record.check_out_lat = lat
        record.check_out_lng = lng
        notes = serializer.validated_data.get("notes", "")
        if notes:
            record.notes = notes
        record.save(update_fields=["check_out", "check_out_lat", "check_out_lng", "notes"])

        return Response(AttendanceRecordSerializer(record).data)
class StartBreakView(APIView):
    """Start a break (Tea / Lunch / Other)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"], request=StartBreakSerializer)
    def post(self, request):
        serializer = StartBreakSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        record = AttendanceRecord.objects.filter(
            employee=request.user, date=date.today(), is_deleted=False
        ).first()
        if not record or not record.check_in:
            return Response({"detail": "Not checked in today."}, status=status.HTTP_400_BAD_REQUEST)
        if record.check_out:
            return Response({"detail": "Day already ended."}, status=status.HTTP_400_BAD_REQUEST)

        active = AttendanceBreak.objects.filter(
            attendance=record, end_time__isnull=True, is_deleted=False
        ).first()
        if active:
            return Response({"detail": "Already on a break. Resume first."}, status=status.HTTP_400_BAD_REQUEST)

        AttendanceBreak.objects.create(
            attendance=record,
            break_type=serializer.validated_data.get("break_type", BreakType.OTHER),
            start_time=dt.datetime.now().time(),
        )
        record.refresh_from_db()
        return Response(AttendanceRecordSerializer(record).data)


class EndBreakView(APIView):
    """End the active break (Resume work)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"])
    def post(self, request):
        record = AttendanceRecord.objects.filter(
            employee=request.user, date=date.today(), is_deleted=False
        ).first()
        if not record:
            return Response({"detail": "No attendance record today."}, status=status.HTTP_400_BAD_REQUEST)

        active = AttendanceBreak.objects.filter(
            attendance=record, end_time__isnull=True, is_deleted=False
        ).first()
        if not active:
            return Response({"detail": "Not on a break."}, status=status.HTTP_400_BAD_REQUEST)

        end_time = dt.datetime.now().time()

        # ── Break duration limit enforcement ──────────────────────────────────
        max_minutes = BREAK_MAX_MINUTES.get(active.break_type, 60)
        start_dt    = dt.datetime.combine(dt.date.today(), active.start_time)
        end_dt      = dt.datetime.combine(dt.date.today(), end_time)
        if end_dt < start_dt:
            end_dt += dt.timedelta(days=1)
        actual_minutes = int((end_dt - start_dt).seconds / 60)

        if actual_minutes > max_minutes:
            break_label = active.get_break_type_display()
            return Response(
                {
                    "detail": (
                        f"{break_label} exceeded the allowed {max_minutes} min limit "
                        f"(you took {actual_minutes} min). "
                        f"Please get manager approval."
                    ),
                    "break_type":     active.break_type,
                    "max_minutes":    max_minutes,
                    "actual_minutes": actual_minutes,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ── Consolidated break check ──────────────────────────────────────────
        completed_same_type = AttendanceBreak.objects.filter(
            attendance=record,
            break_type=active.break_type,
            end_time__isnull=False,
            is_deleted=False,
        ).exclude(pk=active.pk)

        total_prev = sum(b.duration_minutes for b in completed_same_type)
        if total_prev + actual_minutes > max_minutes:
            remaining = max(0, max_minutes - total_prev)
            return Response(
                {
                    "detail": (
                        f"Total {active.get_break_type_display()} for today would exceed "
                        f"{max_minutes} min (already used {total_prev} min, "
                        f"only {remaining} min remaining)."
                    ),
                    "break_type":     active.break_type,
                    "max_minutes":    max_minutes,
                    "used_minutes":   total_prev,
                    "actual_minutes": actual_minutes,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        active.end_time = end_time
        active.save(update_fields=["end_time"])
        record.refresh_from_db()
        return Response(AttendanceRecordSerializer(record).data)


class MonthlyAttendanceView(APIView):
    """Monthly attendance summary for current user."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"])
    def get(self, request):
        today = date.today()
        year  = int(request.query_params.get("year",  today.year))
        month = int(request.query_params.get("month", today.month))

        records = AttendanceRecord.objects.filter(
            employee=request.user, date__year=year, date__month=month, is_deleted=False
        ).prefetch_related("breaks")
        summary = {
            "present":  records.filter(status=AttendanceStatus.PRESENT).count(),
            "absent":   records.filter(status=AttendanceStatus.ABSENT).count(),
            "wfh":      records.filter(status=AttendanceStatus.WFH).count(),
            "half_day": records.filter(status=AttendanceStatus.HALF_DAY).count(),
            "on_leave": records.filter(status=AttendanceStatus.ON_LEAVE).count(),
            "holiday":  records.filter(status=AttendanceStatus.HOLIDAY).count(),
        }
        records_data = AttendanceRecordSerializer(records.order_by("date"), many=True).data
        return Response({"summary": summary, "records": records_data})


# ── Admin / Manager views ─────────────────────────────────────────────────────

class AttendanceOverviewView(APIView):
    """
    GET /attendance/overview/?date=YYYY-MM-DD
    Returns org-wide summary cards + per-status counts for pie chart.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date", str(date.today()))
        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.models import Employee
        total_employees = Employee.objects.filter(is_active=True, is_deleted=False).count()

        records    = AttendanceRecord.objects.filter(date=target_date, is_deleted=False)
        counts     = {s: 0 for s in AttendanceStatus.values}
        for r in records.values("status"):
            counts[r["status"]] = counts.get(r["status"], 0) + 1

        marked     = records.count()
        not_marked = max(0, total_employees - marked)
        counts["NOT_MARKED"] = not_marked

        week_trend = []
        for i in range(6, -1, -1):
            d        = target_date - dt.timedelta(days=i)
            day_recs = AttendanceRecord.objects.filter(date=d, is_deleted=False)
            week_trend.append({
                "date":    d.strftime("%d %b"),
                "present": day_recs.filter(status__in=[AttendanceStatus.PRESENT, AttendanceStatus.WFH]).count(),
                "absent":  day_recs.filter(status=AttendanceStatus.ABSENT).count(),
            })

        return Response({
            "date":            date_str,
            "total_employees": total_employees,
            "marked":          marked,
            "not_marked":      not_marked,
            "counts":          counts,
            "week_trend":      week_trend,
        })


class AttendanceTrackerView(APIView):
    """
    Manager/PMO: full timeline for an employee on a specific date.
    GET  /attendance/tracker/?employee=<id>&date=YYYY-MM-DD
    POST /attendance/tracker/  { employee, date, status, check_in?, check_out?, notes? }
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"])
    def post(self, request):
        employee_id = request.data.get("employee")
        date_str    = request.data.get("date")
        status_val  = request.data.get("status", AttendanceStatus.PRESENT)
        check_in    = request.data.get("check_in")
        check_out   = request.data.get("check_out")
        notes       = request.data.get("notes", "")

        if not employee_id or not date_str:
            return Response({"detail": "employee and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from apps.accounts.models import Employee
            emp = Employee.objects.get(id=employee_id, is_deleted=False)
        except Exception:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        def parse_time(val):
            if not val:
                return None
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return dt.datetime.strptime(val, fmt).time()
                except ValueError:
                    continue
            raise ValueError(f"Invalid time: {val}")

        try:
            ci = parse_time(check_in)
            co = parse_time(check_out)
        except ValueError as e:
            return Response({"detail": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        record, _ = AttendanceRecord.objects.update_or_create(
            employee=emp,
            date=target_date,
            defaults={
                "status":    status_val,
                "check_in":  ci,
                "check_out": co,
                "notes":     notes,
                "is_deleted": False,
            },
        )
        return Response({"detail": "Attendance saved.", "id": str(record.id)}, status=status.HTTP_200_OK)

    @extend_schema(tags=["attendance"])
    def get(self, request):
        employee_id = request.query_params.get("employee")
        date_str    = request.query_params.get("date", str(date.today()))

        if not employee_id:
            return Response({"detail": "employee param required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            from apps.accounts.models import Employee
            emp = Employee.objects.select_related(
                "designation_ref", "department_ref"
            ).get(id=employee_id, is_deleted=False)
        except Exception:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        emp_info = {
            "id":            str(emp.id),
            "full_name":     emp.full_name,
            "employee_code": emp.employee_code,
            "designation":   emp.designation_ref.name if emp.designation_ref_id else (emp.designation or ""),
            "department":    emp.department_ref.name  if emp.department_ref_id  else (emp.department  or ""),
        }

        record = AttendanceRecord.objects.filter(
            employee=emp, date=target_date, is_deleted=False
        ).prefetch_related("breaks").first()

        if not record:
            return Response({"employee": emp_info, "date": date_str, "record": None, "events": []})

        events = []
        if record.check_in:
            events.append({
                "type":  "CHECK_IN",
                "time":  record.check_in.strftime("%H:%M"),
                "label": "Started Day",
                "lat":   float(record.check_in_lat) if record.check_in_lat else None,
                "lng":   float(record.check_in_lng) if record.check_in_lng else None,
            })

        for b in record.breaks.filter(is_deleted=False).order_by("start_time"):
            events.append({
                "type":       "BREAK_START",
                "time":       b.start_time.strftime("%H:%M"),
                "break_type": b.break_type,
                "label":      f"{b.get_break_type_display()} started",
            })
            if b.end_time:
                events.append({
                    "type":             "BREAK_END",
                    "time":             b.end_time.strftime("%H:%M"),
                    "break_type":       b.break_type,
                    "label":            f"{b.get_break_type_display()} ended",
                    "duration_minutes": b.duration_minutes,
                })

        if record.check_out:
            events.append({
                "type":  "CHECK_OUT",
                "time":  record.check_out.strftime("%H:%M"),
                "label": "Ended Day",
                "lat":   float(record.check_out_lat) if record.check_out_lat else None,
                "lng":   float(record.check_out_lng) if record.check_out_lng else None,
            })

        events.sort(key=lambda e: e["time"])

        record_data = {
            "status":              record.status,
            "check_in":            record.check_in.strftime("%H:%M")  if record.check_in  else None,
            "check_out":           record.check_out.strftime("%H:%M") if record.check_out else None,
            "duration_hours":      record.duration_hours,
            "working_hours":       record.working_hours,
            "total_break_minutes": record.total_break_minutes,
            "check_in_lat":        float(record.check_in_lat)  if record.check_in_lat  else None,
            "check_in_lng":        float(record.check_in_lng)  if record.check_in_lng  else None,
            "check_out_lat":       float(record.check_out_lat) if record.check_out_lat else None,
            "check_out_lng":       float(record.check_out_lng) if record.check_out_lng else None,
            "breaks": [
                {
                    "id":               str(b.id),
                    "break_type":       b.break_type,
                    "break_type_label": b.get_break_type_display(),
                    "start_time":       b.start_time.strftime("%H:%M"),
                    "end_time":         b.end_time.strftime("%H:%M") if b.end_time else None,
                    "duration_minutes": b.duration_minutes,
                }
                for b in record.breaks.filter(is_deleted=False).order_by("start_time")
            ],
        }

        return Response({"employee": emp_info, "date": date_str, "record": record_data, "events": events})


class AttendanceExportView(APIView):
    """
    Export monthly attendance as a horizontal pivot CSV.
    GET /attendance/export/?year=2025&month=5
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today      = date.today()
        year       = int(request.query_params.get("year",  today.year))
        month      = int(request.query_params.get("month", today.month))
        month_name = date(year, month, 1).strftime("%B")

        from apps.accounts.models import Employee
        employees = Employee.objects.filter(
            is_active=True, is_deleted=False
        ).exclude(employee_code="").select_related(
            "designation_ref", "department_ref"
        ).order_by("first_name")

        _, num_days = calendar.monthrange(year, month)
        all_dates   = [date(year, month, d) for d in range(1, num_days + 1)]

        all_records = AttendanceRecord.objects.filter(
            date__year=year, date__month=month, is_deleted=False
        ).select_related("employee").prefetch_related("breaks")

        rec_map: dict[tuple, AttendanceRecord] = {}
        for rec in all_records:
            rec_map[(str(rec.employee_id), rec.date)] = rec

        output = io.StringIO()
        output.write('\ufeff')  # UTF-8 BOM for Excel/LibreOffice
        writer = csv.writer(output)

        writer.writerow([f"Attendance Report — {month_name} {year}", ""])
        writer.writerow([])

        fixed_headers   = ["Emp Code", "Full Name", "Designation", "Department"]
        day_headers     = [f"{d.day:02d} {d.strftime('%a')}" for d in all_dates]
        summary_headers = ["Present", "WFH", "Half Day", "On Leave", "Absent", "Holidays", "Working Hrs"]
        writer.writerow(fixed_headers + day_headers + summary_headers)

        for emp in employees:
            desig = emp.designation_ref.name if emp.designation_ref_id else (emp.designation or "")
            dept  = emp.department_ref.name  if emp.department_ref_id  else (emp.department  or "")

            cnt = {k: 0 for k in ("present", "wfh", "half_day", "on_leave", "absent", "holiday")}
            total_working_hrs = 0.0
            day_cells = []

            for d in all_dates:
                rec = rec_map.get((str(emp.id), d))
                if rec:
                    stat = rec.status
                    code = STATUS_CODE.get(stat, stat)
                    if rec.check_in and stat in ("PRESENT", "WFH", "HALF_DAY"):
                        code = f"{code} {rec.check_in.strftime('%H:%M')}"
                    total_working_hrs += rec.working_hours
                else:
                    stat = "WEEKEND" if d.weekday() >= 5 else "ABSENT"
                    code = STATUS_CODE.get(stat, stat)

                stat_key = stat.lower()
                if stat_key in cnt:
                    cnt[stat_key] += 1
                day_cells.append(code)

            summary_cells = [
                cnt["present"], cnt["wfh"], cnt["half_day"],
                cnt["on_leave"], cnt["absent"], cnt["holiday"],
                round(total_working_hrs, 2),
            ]
            writer.writerow([emp.employee_code, emp.full_name, desig, dept] + day_cells + summary_cells)

        writer.writerow([])
        writer.writerow(["Legend:",
            "P=Present", "WFH=Work From Home", "HD=Half Day",
            "OL=On Leave", "HOL=Holiday", "—=Weekend", "ABS=Absent",
        ])

        ts       = today.strftime("%Y_%m_%d_%H%M")
        filename = f"attendance_report_{year}_{str(month).zfill(2)}_{ts}.csv"
        response = HttpResponse(output.getvalue(), content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response


class AttendanceListView(APIView):
    """
    HR/Admin: paginated flat list of attendance records.
    GET /attendance/list/?date=YYYY-MM-DD
    GET /attendance/list/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import Employee

        date_str      = request.query_params.get("date")
        date_from_str = request.query_params.get("date_from")
        date_to_str   = request.query_params.get("date_to")
        today         = date.today()

        if date_str:
            try:
                target    = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)
            date_from = date_to = target
        elif date_from_str and date_to_str:
            try:
                date_from = dt.datetime.strptime(date_from_str, "%Y-%m-%d").date()
                date_to   = dt.datetime.strptime(date_to_str,   "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date_from or date_to."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            date_from = date_to = today

        if (date_to - date_from).days > 366:
            return Response({"detail": "Date range cannot exceed 366 days."}, status=status.HTTP_400_BAD_REQUEST)

        dept_filter = request.query_params.get("department", "").strip()

        emp_qs = Employee.objects.filter(is_active=True, is_deleted=False).select_related(
            "designation_ref", "department_ref", "shift_category"
        )
        if dept_filter:
            emp_qs = emp_qs.filter(
                Q(department_ref__name__iexact=dept_filter) |
                Q(department__iexact=dept_filter)
            )

        records_qs = AttendanceRecord.objects.filter(
            date__gte=date_from, date__lte=date_to, is_deleted=False
        ).select_related("employee")

        rec_map: dict[tuple, AttendanceRecord] = {}
        for rec in records_qs:
            rec_map[(str(rec.employee_id), rec.date)] = rec

        rows = []
        for emp in emp_qs:
            dept_name  = emp.department_ref.name  if emp.department_ref_id  else (emp.department  or "")
            desig_name = emp.designation_ref.name if emp.designation_ref_id else (emp.designation or "")
            shift_name = emp.shift_category.name  if getattr(emp, "shift_category_id", None) else None

            current = date_from
            while current <= date_to:
                rec = rec_map.get((str(emp.id), current))
                if rec:
                    row_status    = rec.status
                    check_in_val  = rec.check_in.strftime("%H:%M")  if rec.check_in  else None
                    check_out_val = rec.check_out.strftime("%H:%M") if rec.check_out else None
                    working_hrs   = rec.working_hours
                else:
                    row_status    = AttendanceStatus.WEEKEND if current.weekday() >= 5 else "NOT_MARKED"
                    check_in_val  = None
                    check_out_val = None
                    working_hrs   = 0.0

                rows.append({
                    "id":            str(rec.id) if rec else None,
                    "employee_id":   str(emp.id),
                    "employee_name": emp.full_name,
                    "employee_code": emp.employee_code,
                    "department":    dept_name,
                    "division":      "",
                    "date":          current.isoformat(),
                    "status":        row_status,
                    "check_in":      check_in_val,
                    "check_out":     check_out_val,
                    "working_hours": working_hrs,
                    "shift_name":    shift_name,
                })
                current += dt.timedelta(days=1)

        try:
            page_size = min(int(request.query_params.get("page_size", 100)), 1000)
        except ValueError:
            page_size = 100

        return Response({"count": len(rows), "results": rows[:page_size]})


# ── Leave views ───────────────────────────────────────────────────────────────

class LeaveTypeListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["leave"])
    def get(self, request):
        types = LeaveType.objects.filter(is_active=True)
        return Response(LeaveTypeSerializer(types, many=True).data)

    @extend_schema(tags=["leave"])
    def post(self, request):
        serializer = LeaveTypeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class MyLeaveBalancesView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["leave"])
    def get(self, request):
        year     = int(request.query_params.get("year", date.today().year))
        balances = LeaveBalance.objects.filter(
            employee=request.user, year=year
        ).select_related("leave_type")
        return Response(LeaveBalanceSerializer(balances, many=True).data)


class MyLeaveRequestListView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["leave"])
    def get(self, request):
        qs = LeaveRequest.objects.filter(
            employee=request.user, is_deleted=False
        ).select_related("leave_type", "reviewer").order_by("-created_at")[:20]
        return Response(LeaveRequestSerializer(qs, many=True).data)

    @extend_schema(tags=["leave"], request=LeaveRequestSerializer)
    def post(self, request):
        serializer = LeaveRequestSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        leave = serializer.save(employee=request.user)

        is_ceo = (request.user.designation_ref and request.user.designation_ref.name.lower() == "ceo") or (request.user.designation and request.user.designation.lower() == "ceo")
        if is_ceo:
            leave.status = LeaveRequestStatus.APPROVED
            leave.reviewer = request.user
            leave.reviewer_remarks = "Auto-approved as CEO"
            leave.save()

        # Get project managers for the employee
        from .leave_utils import get_project_managers_for_employee
        project_managers = get_project_managers_for_employee(request.user)
        
        # Send notifications to project managers
        if project_managers:
            leave.is_acknowledged = False
            leave.save(update_fields=['is_acknowledged'])
            for manager in project_managers:
                publish_event(
                    EventType.LEAVE_REQUESTED,
                    ReferenceType.LEAVE,
                    str(leave.id),
                    payload={
                        "employee_id": str(request.user.id),
                        "employee_name": request.user.full_name,
                        "leave_type": leave.leave_type.name if leave.leave_type else "",
                        "start_date": leave.start_date.isoformat(),
                        "end_date": leave.end_date.isoformat(),
                        "days_count": leave.days_count,
                        "notification_target": "project_manager",
                        "project_manager_id": str(manager.id),
                    },
                    actor_id=str(request.user.id),
                    recipient_ids=[str(manager.id)],
                    async_delivery=True,
                )
        else:
            leave.is_acknowledged = True
            leave.save(update_fields=['is_acknowledged'])
            publish_event(
                EventType.LEAVE_REQUESTED,
                ReferenceType.LEAVE,
                str(leave.id),
                payload={
                    "employee_id": str(request.user.id),
                    "employee_name": request.user.full_name,
                    "leave_type": leave.leave_type.name if leave.leave_type else "",
                    "start_date": leave.start_date.isoformat(),
                    "end_date": leave.end_date.isoformat(),
                    "days_count": leave.days_count,
                },
                actor_id=str(request.user.id),
                async_delivery=True,
            )
        

        return Response(LeaveRequestSerializer(leave).data, status=status.HTTP_201_CREATED)


class LeaveRequestDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def _get_leave(self, pk, user):
        try:
            return LeaveRequest.objects.get(pk=pk, employee=user, is_deleted=False)
        except LeaveRequest.DoesNotExist:
            return None

    @extend_schema(tags=["leave"])
    def delete(self, request, pk):
        leave = self._get_leave(pk, request.user)
        if not leave:
            return Response(status=status.HTTP_404_NOT_FOUND)
        if leave.status not in (LeaveRequestStatus.PENDING, LeaveRequestStatus.APPROVED):
            return Response({"detail": "Cannot cancel this request."}, status=status.HTTP_400_BAD_REQUEST)
        leave.status = LeaveRequestStatus.CANCELLED
        leave.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


def get_reporting_hierarchy_map(manager):
    all_employees = list(account_models.Employee.objects.filter(is_active=True, is_deleted=False))
    
    by_manager = {}
    for emp in all_employees:
        if emp.manager_id:
            by_manager.setdefault(str(emp.manager_id), []).append(emp)
            
    direct = by_manager.get(str(manager.id), [])
    reporting_map = {}
    
    for d in direct:
        reporting_map[str(d.id)] = "direct"
        
    queue = [(d, "indirect") for d in direct]
    while queue:
        curr, level = queue.pop(0)
        children = by_manager.get(str(curr.id), [])
        for child in children:
            if str(child.id) not in reporting_map:
                reporting_map[str(child.id)] = "indirect"
                queue.append((child, "indirect"))
                
    return reporting_map


def is_in_manager_chain(manager, employee):
    curr = employee
    visited = set()
    while curr.manager and curr.manager not in visited:
        if curr.manager == manager:
            return True
        visited.add(curr.manager)
        curr = curr.manager
    return False


class LeaveAcknowledgeView(APIView):
    permission_classes = [IsAuthenticated]
    
    @extend_schema(tags=["leave"])
    def post(self, request, pk):
        try:
            leave = LeaveRequest.objects.get(pk=pk, is_deleted=False)
        except LeaveRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)
            
        if leave.status != LeaveRequestStatus.PENDING or leave.is_acknowledged:
            return Response({"detail": "Cannot acknowledge this request."}, status=status.HTTP_400_BAD_REQUEST)
            
        from .leave_utils import get_project_managers_for_employee
        project_managers = get_project_managers_for_employee(leave.employee)
        is_pm = any(manager.id == request.user.id for manager in project_managers)
        
        if not is_pm:
            return Response({"detail": "Only project managers can acknowledge."}, status=status.HTTP_403_FORBIDDEN)
            
        remarks = request.data.get("remarks", "").strip()
        if remarks:
            leave.reviewer_remarks = f"PM Acknowledged: {remarks}"
            
        leave.is_acknowledged = True
        leave.save(update_fields=['is_acknowledged', 'reviewer_remarks'])
        
        from apps.notifications.constants import EventType, ReferenceType
        from apps.notifications.publisher import publish_event
        publish_event(
            EventType.LEAVE_REQUESTED,
            ReferenceType.LEAVE,
            str(leave.id),
            payload={
                "employee_id": str(leave.employee.id),
                "employee_name": leave.employee.full_name,
                "leave_type": leave.leave_type.name if leave.leave_type else "",
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "days_count": float(leave.days_count),
            },
            actor_id=str(request.user.id),
            async_delivery=True,
        )
        return Response({"detail": "Acknowledged successfully"})

class LeaveReviewView(APIView):
    """Project managers can review leave requests of employees assigned to their projects."""
    permission_classes = [IsAuthenticated]

    def _is_authorized_reviewer(self, reviewer, employee):
        """Check if the reviewer is a project manager for the employee."""
        from .leave_utils import get_project_managers_for_employee
        
        # Get project managers for the employee
        project_managers = get_project_managers_for_employee(employee)
        
        # Check if reviewer is one of the project managers
        return any(manager.id == reviewer.id for manager in project_managers)

    @extend_schema(tags=["leave"], request=LeaveReviewSerializer)
    def post(self, request, pk):
        try:
            leave = LeaveRequest.objects.get(pk=pk, is_deleted=False)
        except LeaveRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if leave.status != LeaveRequestStatus.PENDING:
            return Response({"detail": "Only PENDING requests can be reviewed."}, status=status.HTTP_400_BAD_REQUEST)

        is_ceo = (request.user.designation_ref and request.user.designation_ref.name.lower() == "ceo") or (request.user.designation and request.user.designation.lower() == "ceo")

        # Disable self-approval for non-CEOs
        if leave.employee == request.user and not is_ceo:
            return Response({"detail": "You cannot approve your own leave request."}, status=status.HTTP_400_BAD_REQUEST)

        # Only HR can approve (or CEO for their own leave)
        is_hr = request.user.keycloak_group and request.user.keycloak_group.lower() == "hr"
        is_authorized = is_hr
        
        if is_ceo and leave.employee == request.user:
            is_authorized = True

        if not is_authorized:
            return Response(
                {"detail": "You are not authorized to review this leave request. Only HR can approve."},
                status=status.HTTP_403_FORBIDDEN
            )

        serializer = LeaveReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        leave.status           = serializer.validated_data["status"]
        leave.reviewer         = request.user
        leave.reviewer_remarks = serializer.validated_data.get("remarks", "")
        leave.save(update_fields=["status", "reviewer", "reviewer_remarks"])

        if leave.status == LeaveRequestStatus.APPROVED:
            # ── Skip balance deduction if exempt (emergency leave with medical certificate) ──
            if not getattr(leave, "exempt_from_balance", False):
                balance, _ = LeaveBalance.objects.get_or_create(
                    employee=leave.employee,
                    leave_type=leave.leave_type,
                    year=leave.start_date.year,
                    defaults={"total_days": leave.leave_type.max_days, "used_days": 0},
                )
                balance.used_days = float(balance.used_days) + float(leave.days_count)
                balance.save(update_fields=["used_days"])

        # Send notification about the review decision
        from apps.notifications.constants import EventType, ReferenceType
        from apps.notifications.publisher import publish_event
        
        if leave.status == LeaveRequestStatus.APPROVED:
            event_type = EventType.LEAVE_APPROVED
        else:
            event_type = EventType.LEAVE_REJECTED
            
        publish_event(
            event_type,
            ReferenceType.LEAVE,
            str(leave.id),
            payload={
                "employee_id": str(leave.employee.id),
                "employee_name": leave.employee.full_name,
                "reviewer_id": str(request.user.id),
                "reviewer_name": request.user.full_name,
                "leave_type": leave.leave_type.name if leave.leave_type else "",
                "start_date": leave.start_date.isoformat(),
                "end_date": leave.end_date.isoformat(),
                "days_count": leave.days_count,
                "status": leave.status,
                "remarks": leave.reviewer_remarks,
            },
            actor_id=str(request.user.id),
            recipient_ids=[str(leave.employee.id)],  # Notify the employee
            async_delivery=True,
        )

        return Response(LeaveRequestSerializer(leave).data)


class LeaveTeamMetaView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["leave"])
    def get(self, request):
        reporting_map = get_reporting_hierarchy_map(request.user)
        direct_count = sum(1 for lvl in reporting_map.values() if lvl == "direct")
        indirect_count = sum(1 for lvl in reporting_map.values() if lvl == "indirect")
        return Response({
            "has_team": len(reporting_map) > 0,
            "direct_count": direct_count,
            "indirect_count": indirect_count,
        })


class LeaveTeamRequestsView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["leave"])
    def get(self, request):
        reporting_map = get_reporting_hierarchy_map(request.user)
        
        from apps.allocation.models import Allocation
        pm_allocations = Allocation.objects.filter(
            project__manager=request.user,
            is_deleted=False,
            is_active=True
        ).exclude(employee=request.user)
        
        pm_emp_ids = set()
        for alloc in pm_allocations:
            pm_emp_ids.add(str(alloc.employee_id))
            if str(alloc.employee_id) not in reporting_map:
                reporting_map[str(alloc.employee_id)] = "project"

        if not reporting_map:
            return Response({
                "pending_count": 0,
                "direct_count": 0,
                "indirect_count": 0,
                "results": [],
            })

        status_filter = request.query_params.get("status")
        qs = LeaveRequest.objects.filter(employee_id__in=reporting_map.keys(), is_deleted=False).select_related(
            "employee", "leave_type"
        ).order_by("-created_at")

        if status_filter:
            if status_filter in ("PENDING", "PENDING_MANAGER"):
                qs = qs.filter(status="PENDING")
            else:
                qs = qs.filter(status=status_filter)

        direct_report_ids = [eid for eid, lvl in reporting_map.items() if lvl == "direct"]
        direct_count = sum(1 for lvl in reporting_map.values() if lvl == "direct")
        indirect_count = sum(1 for lvl in reporting_map.values() if lvl == "indirect")
        pending_count = LeaveRequest.objects.filter(
            employee_id__in=direct_report_ids,
            status="PENDING",
            is_deleted=False
        ).count()

        results = []
        for lr in qs:
            lvl = reporting_map[str(lr.employee_id)]
            is_hr = request.user.keycloak_group and request.user.keycloak_group.lower() == "hr"
            can_approve = is_hr and (lr.status == "PENDING") and (lr.employee != request.user) and lr.is_acknowledged
            can_ack = str(lr.employee_id) in pm_emp_ids and not lr.is_acknowledged and (lr.status == "PENDING")
            results.append({
                "id": str(lr.id),
                "employee": lr.employee.full_name,
                "employee_code": lr.employee.employee_code,
                "leave_type": lr.leave_type.name,
                "color": lr.leave_type.color,
                "start_date": str(lr.start_date),
                "end_date": str(lr.end_date),
                "days_count": float(lr.days_count),
                "reason": lr.reason,
                "status": lr.status,
                "acknowledged_by": None,
                "ack_project": None,
                "created_at": str(lr.created_at.date()),
                "reporting_level": lvl,
                "can_approve": can_approve,
                "can_ack": can_ack,
                "can_view_only": not (can_approve or can_ack),
            })

        return Response({
            "pending_count": pending_count,
            "direct_count": direct_count,
            "indirect_count": indirect_count,
            "results": results,
        })


class AdminLeaveRequestListView(APIView):
    """HR / PMO view — all employees' leave requests with summary stats."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.allocation.models import Allocation
        pm_allocations = Allocation.objects.filter(
            project__manager=request.user, is_deleted=False, is_active=True
        ).exclude(employee=request.user)
        pm_emp_ids = {str(a.employee_id) for a in pm_allocations}
        
        qs = LeaveRequest.objects.filter(is_deleted=False).select_related(
            "employee", "leave_type", "reviewer"
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")
        employee_id   = request.query_params.get("employee")
        if status_filter:
            qs = qs.filter(status=status_filter)
        if employee_id:
            qs = qs.filter(employee_id=employee_id)

        all_qs  = LeaveRequest.objects.filter(is_deleted=False)
        summary = {
            "pending":       all_qs.filter(status=LeaveRequestStatus.PENDING).count(),
            "approved":      all_qs.filter(status=LeaveRequestStatus.APPROVED).count(),
            "rejected":      all_qs.filter(status=LeaveRequestStatus.REJECTED).count(),
            "days_approved": float(
                all_qs.filter(status=LeaveRequestStatus.APPROVED)
                .aggregate(t=Sum("days_count"))["t"] or 0
            ),
        }

        data = [
            {
                "id":               str(lr.id),
                "employee_id":      str(lr.employee_id),
                "employee":         lr.employee.full_name,
                "leave_type":       lr.leave_type.name,
                "color":            lr.leave_type.color,
                "start_date":       str(lr.start_date),
                "end_date":         str(lr.end_date),
                "days_count":       float(lr.days_count),
                "reason":           lr.reason,
                "status":           lr.status,
                "reviewer":         lr.reviewer.full_name if lr.reviewer_id else None,
                "reviewer_remarks": lr.reviewer_remarks,
                "created_at":       str(lr.created_at.date()),
                "can_approve":      (lr.status == LeaveRequestStatus.PENDING) and (lr.employee != request.user) and (request.user.keycloak_group and request.user.keycloak_group.lower() == "hr") and lr.is_acknowledged,
                "can_ack":          (lr.status == LeaveRequestStatus.PENDING) and not lr.is_acknowledged and (str(lr.employee_id) in pm_emp_ids),
            }
            for lr in qs
        ]

        return Response({"summary": summary, "results": data})


class LeaveAssignView(APIView):
    """HR — assign a leave type's balance to one or more employees for a financial year."""
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.hrms.leave.manage"

    def get(self, request):
        from apps.dashboard.fy_utils import fy_bounds, fy_label, current_fy_start
        from apps.master.models import Holiday
        from datetime import timedelta
        
        year_param = request.query_params.get("year")
        if year_param:
            try:
                year = int(year_param)
            except ValueError:
                return Response({"detail": "Invalid year format."}, status=status.HTTP_400_BAD_REQUEST)
            
            start_date, end_date = fy_bounds(year)
            holidays = set(
                Holiday.objects.filter(
                    date__gte=start_date,
                    date__lte=end_date,
                    is_active=True,
                ).values_list("date", flat=True)
            )
            
            working_days = 0
            current = start_date
            while current <= end_date:
                if current.weekday() < 5 and current not in holidays:
                    working_days += 1
                current += timedelta(days=1)
            
            return Response({
                "financial_year": year,
                "fy_label": fy_label(year),
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "total_days": (end_date - start_date).days + 1,
                "working_days": working_days,
                "holidays_count": len(holidays),
            })
            
        current_year = current_fy_start()
        res_years = []
        for year in range(current_year - 2, current_year + 3):
            start_date, end_date = fy_bounds(year)
            holidays = set(
                Holiday.objects.filter(
                    date__gte=start_date,
                    date__lte=end_date,
                    is_active=True,
                ).values_list("date", flat=True)
            )
            working_days = 0
            current = start_date
            while current <= end_date:
                if current.weekday() < 5 and current not in holidays:
                    working_days += 1
                current += timedelta(days=1)
                
            res_years.append({
                "year": year,
                "label": fy_label(year),
                "working_days": working_days,
            })
            
        return Response({"available_years": res_years})

    def post(self, request):
        from decimal import Decimal, InvalidOperation
        from apps.dashboard.fy_utils import current_fy_start, fy_label
        from .leave_utils import eligible_carry_forward_days

        data          = request.data
        leave_type_id = data.get("leave_type_id")
        total_days    = data.get("total_days")
        carry_forward = bool(data.get("carry_forward", False))
        employee_ids  = data.get("employee_ids") or []

        is_ceo = (request.user.designation_ref and request.user.designation_ref.name.lower() == "ceo") or (request.user.designation and request.user.designation.lower() == "ceo")
        if any(str(eid) == str(request.user.id) for eid in employee_ids) and not is_ceo:
            return Response({"detail": "You cannot assign leave balance to yourself."}, status=status.HTTP_400_BAD_REQUEST)

        errors = {}
        if not leave_type_id:
            errors["leave_type_id"] = "This field is required."
        if total_days is None or total_days == "":
            errors["total_days"] = "This field is required."
        if not employee_ids:
            errors["employee_ids"] = "Select at least one employee."
        if errors:
            return Response({"detail": "Validation failed", "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        try:
            total_days = Decimal(str(total_days))
            if total_days < 0:
                raise InvalidOperation
        except InvalidOperation:
            return Response({"detail": "Validation failed", "errors": {"total_days": "Must be a non-negative number."}}, status=status.HTTP_400_BAD_REQUEST)

        try:
            leave_type = LeaveType.objects.get(id=leave_type_id, is_active=True)
        except LeaveType.DoesNotExist:
            return Response({"detail": "Leave type not found or inactive."}, status=status.HTTP_400_BAD_REQUEST)

        fy_raw = data.get("financial_year")
        fy_start_year = int(fy_raw) if fy_raw else current_fy_start()

        employees  = list(account_models.Employee.objects.filter(id__in=employee_ids, is_deleted=False))
        found_ids  = {str(e.id) for e in employees}
        missing_ids = [eid for eid in employee_ids if str(eid) not in found_ids]

        counts  = {"assigned": 0, "duplicate": 0, "max_days_exceeded": 0, "error": 0}
        results = []

        for emp in employees:
            cf_days     = eligible_carry_forward_days(emp, leave_type, fy_start_year) if carry_forward else Decimal("0")
            final_total = total_days + cf_days

            if LeaveBalance.objects.filter(employee=emp, leave_type=leave_type, year=fy_start_year).exists():
                counts["duplicate"] += 1
                results.append({
                    "employee_id": str(emp.id), "employee_name": emp.full_name,
                    "status": "duplicate",
                    "message": f"Already assigned for {fy_label(fy_start_year)}.",
                })
                continue

            if leave_type.max_days and final_total > leave_type.max_days:
                counts["max_days_exceeded"] += 1
                results.append({
                    "employee_id": str(emp.id), "employee_name": emp.full_name,
                    "status": "max_days_exceeded",
                    "message": f"{final_total} day(s) exceeds the {leave_type.max_days}-day max for {leave_type.name}.",
                })
                continue

            LeaveBalance.objects.create(
                employee=emp, leave_type=leave_type, year=fy_start_year,
                total_days=final_total, used_days=0,
            )
            counts["assigned"] += 1
            results.append({
                "employee_id": str(emp.id), "employee_name": emp.full_name,
                "status": "assigned",
                "message": (
                    f"Assigned {final_total} day(s)"
                    + (f" (incl. {cf_days} carried forward)" if cf_days > 0 else "")
                    + f" for {fy_label(fy_start_year)}."
                ),
                "carry_forward_days": float(cf_days),
                "total_days": float(final_total),
            })

        for eid in missing_ids:
            counts["error"] += 1
            results.append({"employee_id": str(eid), "employee_name": None, "status": "error", "message": "Employee not found."})

        return Response({
            "financial_year": fy_start_year,
            "fy_label":        fy_label(fy_start_year),
            "leave_type_name": leave_type.name,
            "summary":         counts,
            "results":         results,
        })


class EmployeeCalendarView(APIView):
    """
    GET /attendance/employee-calendar/?employee=<id>&year=YYYY&month=MM
    Returns day-by-day calendar data combining attendance records + leave requests.
    """
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"])
    def get(self, request):
        today  = date.today()
        year   = int(request.query_params.get("year",  today.year))
        month  = int(request.query_params.get("month", today.month))
        emp_id = request.query_params.get("employee")

        is_hr           = request.user.is_staff or getattr(request.user, "is_superuser", False)
        hr_perms        = getattr(request, "user_permissions", [])
        can_view_others = is_hr or "pmt.hrms.employee.view" in hr_perms or "pmt.hrms.attendance.view" in hr_perms

        if not emp_id:
            emp_id = str(request.user.id)
        elif not can_view_others and str(request.user.id) != emp_id:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        try:
            from apps.accounts.models import Employee
            emp = Employee.objects.get(id=emp_id, is_deleted=False)
        except Exception:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        _, num_days = calendar.monthrange(year, month)
        all_dates   = [date(year, month, d) for d in range(1, num_days + 1)]

        rec_map = {r.date: r for r in AttendanceRecord.objects.filter(
            employee=emp, date__year=year, date__month=month, is_deleted=False
        )}

        month_start = date(year, month, 1)
        month_end   = date(year, month, num_days)
        leaves_qs   = LeaveRequest.objects.filter(
            employee=emp, is_deleted=False,
            start_date__lte=month_end, end_date__gte=month_start,
        ).select_related("leave_type").exclude(status=LeaveRequestStatus.REJECTED)

        leave_map: dict = {}
        holiday_map = {
                h.date: h
                for h in Holiday.objects.filter(
                    date__year=year, date__month=month, is_active=True
                )
        }
        print("DEBUG holiday_map:", holiday_map)  # Debug print removed
        print("DEBUG holiday count:", len(holiday_map))  # Debug print removed
        for lr in leaves_qs:
            d = lr.start_date
            while d <= lr.end_date:
                if month_start <= d <= month_end:
                    if d not in leave_map or lr.status == LeaveRequestStatus.APPROVED:
                        leave_map[d] = lr
                d += dt.timedelta(days=1)

        days_data      = []
        effective_days = 0.0
        summary        = {s: 0 for s in ["present", "absent", "wfh", "half_day", "on_leave", "holiday", "weekend", "pending_leave"]}

        for d in all_dates:
            weekday    = d.weekday()
            is_weekend = weekday >= 5
            rec        = rec_map.get(d)
            leave      = leave_map.get(d)
            holiday_obj  = holiday_map.get(d)                          # ← moved up, always set
            holiday_type = holiday_obj.holiday_type if holiday_obj else None

            if rec:
                att_status    = rec.status
                check_in      = rec.check_in.strftime("%H:%M")  if rec.check_in  else None
                check_out     = rec.check_out.strftime("%H:%M") if rec.check_out else None
                working_hours = rec.working_hours
                notes         = rec.notes
            else:
                att_status    = AttendanceStatus.WEEKEND if is_weekend else None
                check_in      = None
                check_out     = None
                working_hours = 0.0
                notes         = ""

            if att_status == AttendanceStatus.PRESENT:
                display_status = "PRESENT";  effective_days += 1;   summary["present"]  += 1
            elif att_status == AttendanceStatus.WFH:
                display_status = "WFH";      effective_days += 1;   summary["wfh"]      += 1
            elif att_status == AttendanceStatus.HALF_DAY:
                display_status = "HALF_DAY"; effective_days += 0.5; summary["half_day"] += 1
            elif att_status == AttendanceStatus.ON_LEAVE:
                display_status = "ON_LEAVE";                         summary["on_leave"] += 1
            elif att_status == AttendanceStatus.HOLIDAY:
                display_status = "HOLIDAY";                          summary["holiday"]  += 1
            elif att_status == AttendanceStatus.WEEKEND:
                display_status = "WEEKEND";                          summary["weekend"]  += 1
            elif att_status == AttendanceStatus.ABSENT:
                display_status = "ABSENT";                           summary["absent"]   += 1
            else:
                if is_weekend:
                    display_status = "WEEKEND"; summary["weekend"] += 1
                elif leave:
                    if leave.status == LeaveRequestStatus.PENDING:
                        display_status = "PENDING_LEAVE"; summary["pending_leave"] += 1
                    else:
                        display_status = "ON_LEAVE"; summary["on_leave"] += 1
                elif holiday_obj:
                    display_status = "HOLIDAY"; summary["holiday"] += 1
                elif d > today:
                    display_status = "FUTURE"
                else:
                    display_status = "NOT_MARKED"

            leave_info = None
            if leave:
                leave_info = {
                    "id":         str(leave.id),
                    "type":       leave.leave_type.name,
                    "color":      leave.leave_type.color,
                    "status":     leave.status,
                    "days_count": float(leave.days_count),
                    "reason":     leave.reason,
                }

            days_data.append({
                "date":           d.isoformat(),
                "day":            d.day,
                "weekday":        weekday,
                "is_weekend":     is_weekend,
                "is_today":       d == today,
                "is_future":      d > today,
                "display_status": display_status,
                "att_status":     att_status,
                "check_in":       check_in,
                "check_out":      check_out,
                "working_hours":  working_hours,
                "notes":          notes,
                "leave":          leave_info,
                "holiday_type":   holiday_type,                      # ← always present now
            })

        return Response({
            "year":           year,
            "month":          month,
            "employee_id":    str(emp.id),
            "employee_name":  emp.full_name,
            "effective_days": round(effective_days, 1),
            "summary":        summary,
            "days":           days_data,
        })


# ── Clock-in enable (HR grants permission to no-shift employees) ──────────────

# class AttendanceClockInEnableView(APIView):
#     """
#     GET  /attendance/enable-clockin/?date=YYYY-MM-DD
#     POST /attendance/enable-clockin/  { employee, date, enabled }
#     """
#     permission_classes = [IsAuthenticated]

#     def get(self, request):
#         date_str      = request.query_params.get("date")
#         date_from_str = request.query_params.get("date_from")
#         date_to_str   = request.query_params.get("date_to")

#         try:
#             if date_from_str and date_to_str:
#                 date_from = dt.datetime.strptime(date_from_str, "%Y-%m-%d").date()
#                 date_to   = dt.datetime.strptime(date_to_str,   "%Y-%m-%d").date()
#                 entries = AttendanceClockInEnable.objects.filter(
#                     date__gte=date_from, date__lte=date_to, is_deleted=False
#                 ).select_related("employee", "employee__department_ref", "enabled_by", "shift_category")
#             else:
#                 target_date = dt.datetime.strptime(date_str or str(date.today()), "%Y-%m-%d").date()
#                 entries = AttendanceClockInEnable.objects.filter(
#                     date=target_date, is_deleted=False
#                 ).select_related("employee", "employee__department_ref", "enabled_by", "shift_category")
#         except ValueError:
#             return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)
#         entries = AttendanceClockInEnable.objects.filter(
#             date=target_date, is_deleted=False
#         ).select_related("employee", "employee__department_ref", "enabled_by", "shift_category")

#         results = []
#         for e in entries:
#             emp  = e.employee
#             dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")
#             shift = e.shift_category
#             results.append({
#                 "id":                  str(e.id),
#                 "employee_id":         str(emp.id),
#                 "employee_name":       emp.full_name,
#                 "employee_code":       emp.employee_code,
#                 "department":          dept,
#                 "date":                e.date.isoformat(),
#                 "enabled":             e.enabled,
#                 "enabled_by":          e.enabled_by.full_name if e.enabled_by_id else None,
#                 "shift_category_id":   str(shift.id)         if shift else None,
#                 "shift_category_name": shift.name            if shift else None,
#                 "shift_start_time":    shift.start_time.strftime("%H:%M:%S") if shift else None,
#                 "shift_end_time":      shift.end_time.strftime("%H:%M:%S")   if shift else None,
#                 "job_type":            e.job_type,
#             })

#         return Response({"count": len(results), "results": results})

#     def post(self, request):
#         emp_id     = request.data.get("employee")
#         enabled    = request.data.get("enabled", True)
#         shift_id   = request.data.get("shift_category")
#         job_type   = request.data.get("job_type")

#         # ── NEW: range support ────────────────────────────────────────────
#         date_from  = request.data.get("date_from")
#         date_to    = request.data.get("date_to")
#         single     = request.data.get("date")

#         if date_from and date_to:
#             start = date.fromisoformat(date_from)
#             end   = date.fromisoformat(date_to)
#             dates = []
#             cur   = start
#             while cur <= end:
#                 dates.append(cur)
#                 cur += timedelta(days=1)
#         elif single:
#             dates = [date.fromisoformat(single)]
#         else:
#             return Response({"detail": "Provide date or date_from+date_to"}, status=400)
#         # ─────────────────────────────────────────────────────────────────

#         created = []
#         for d in dates:
#             obj, _ = AttendanceClockInEnable.objects.update_or_create(
#                 employee_id=emp_id,
#                 date=d,
#                 defaults={
#                     "enabled":        enabled,
#                     "shift_category_id": shift_id or None,
#                     "job_type":       job_type or None,
#                     "enabled_by":     request.user,
#                 },
#             )
#             created.append(obj.id)

#         return Response({"created": len(created)}, status=201)
class AttendanceClockInEnableView(APIView):
    permission_classes = [IsAuthenticated]  # Keycloak handles auth via middleware

    def get(self, request):
        date_from_str = request.query_params.get("date_from")
        date_to_str   = request.query_params.get("date_to")
        date_str      = request.query_params.get("date")

        if date_from_str and date_to_str:
            try:
                date_from = dt.datetime.strptime(date_from_str, "%Y-%m-%d").date()
                date_to   = dt.datetime.strptime(date_to_str,   "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date_from or date_to."}, status=status.HTTP_400_BAD_REQUEST)
        elif date_str:
            try:
                date_from = date_to = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)
        else:
            date_from = date_to = date.today()

        # REPLACE WITH — also prefetch shift_category to avoid N+1:
        entries = AttendanceClockInEnable.objects.filter(
            date_from__lte=date_to, date_to__gte=date_from,
            is_deleted=False,
        ).select_related(
            "employee", "employee__department_ref",
            "enabled_by", "shift_category",
        ).order_by("employee__first_name", "date_from")


        results = []
        for e in entries:
            emp  = e.employee
            dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")
            results.append({
                "id":            str(e.id),
                "employee_id":   str(emp.id),
                "employee_name": emp.full_name,
                "employee_code": emp.employee_code,
                "department":    dept,
                # ✅ FIX: e.date is None now — use date_from/date_to instead
                "date":          e.date_from.isoformat() if e.date_from else None,
                "date_from":     e.date_from.isoformat() if e.date_from else None,
                "date_to":       e.date_to.isoformat()   if e.date_to   else None,
                "enabled":       e.enabled,
                "enabled_by":    e.enabled_by.full_name if e.enabled_by_id else None,
                "shift_category_id":   str(e.shift_category_id) if e.shift_category_id else None,
                "shift_category_name": e.shift_category.name       if e.shift_category_id else None,
                "shift_start_time":    e.shift_category.start_time.strftime("%H:%M") if e.shift_category_id else None,
                "shift_end_time":      e.shift_category.end_time.strftime("%H:%M")   if e.shift_category_id else None,
                "job_type":      getattr(e, "job_type", None),
            })
        return Response({"count": len(results), "results": results})

    def post(self, request):
        emp_id        = request.data.get("employee")
        enabled       = request.data.get("enabled", True)
        shift_id      = request.data.get("shift_category")
        job_type      = request.data.get("job_type")
        date_from_str = request.data.get("date_from")
        date_to_str   = request.data.get("date_to")

        if not emp_id:
            return Response({"detail": "employee is required."}, status=status.HTTP_400_BAD_REQUEST)
        if not date_from_str or not date_to_str:
            return Response({"detail": "date_from and date_to are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            date_from = dt.date.fromisoformat(date_from_str)
            date_to   = dt.date.fromisoformat(date_to_str)
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        existing_qs = AttendanceClockInEnable.objects.filter(
            employee_id=emp_id,
            date_from=date_from,
            date_to=date_to,
            is_deleted=False,
        ).order_by("-id")

        obj = existing_qs.first()

        if obj:
            # Soft-delete any duplicate rows beyond the first one
            dup_ids = list(existing_qs.exclude(pk=obj.pk).values_list("id", flat=True))
            if dup_ids:
                AttendanceClockInEnable.objects.filter(id__in=dup_ids).update(is_deleted=True)

            obj.enabled           = bool(enabled)
            obj.shift_category_id = shift_id or None
            obj.job_type          = job_type or None
            obj.enabled_by        = request.user
            obj.save(update_fields=["enabled", "shift_category_id", "job_type", "enabled_by"])
        else:
            obj = AttendanceClockInEnable.objects.create(
                employee_id=emp_id,
                date_from=date_from,
                date_to=date_to,
                enabled=bool(enabled),
                shift_category_id=shift_id or None,
                job_type=job_type or None,
                enabled_by=request.user,
            )
        emp = obj.employee
        dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")
        shift = obj.shift_category

        return Response({
            "id":                  str(obj.id),
            "employee_id":         str(emp.id),
            "employee_name":       emp.full_name,
            "employee_code":       emp.employee_code,
            "department":          dept,
            "date_from":           obj.date_from.isoformat(),
            "date_to":             obj.date_to.isoformat(),
            "enabled":             obj.enabled,
            "enabled_by":          obj.enabled_by.full_name if obj.enabled_by_id else None,
            "shift_category_id":   str(shift.id)   if shift else None,
            "shift_category_name": shift.name       if shift else None,
            "shift_start_time":    shift.start_time.strftime("%H:%M") if shift else None,
            "shift_end_time":      shift.end_time.strftime("%H:%M")   if shift else None,
            "job_type":            obj.job_type,
        }, status=status.HTTP_201_CREATED)

    
class EmployeeShiftView(APIView):
    """
    GET   /attendance/employee-shifts/
    POST  /attendance/employee-shifts/
    PATCH /attendance/employee-shifts/<pk>/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import EmployeeShift

        qs = EmployeeShift.objects.filter(is_deleted=False).select_related(
            "employee", "employee__department_ref", "employee__employment_type", "shift",
        ).order_by("-effective_from")

        emp_id = request.query_params.get("employee")
        if emp_id:
            qs = qs.filter(employee_id=emp_id)

        results = []
        for es in qs:
            emp  = es.employee
            dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")
            results.append({
                "id":              str(es.id),
                "employee_id":     str(emp.id),
                "employee_name":   emp.full_name,
                "employee_code":   emp.employee_code,
                "department":      dept,
                "shift_id":        str(es.shift_id),
                "shift_name":      es.shift.name,
                "start_time":      es.shift.start_time.strftime("%H:%M:%S"),
                "end_time":        es.shift.end_time.strftime("%H:%M:%S"),
                "effective_from":  es.effective_from.isoformat(),
                "effective_to":    es.effective_to.isoformat() if es.effective_to else None,
                "job_type":        es.job_type,
                "employment_type": emp.employment_type.name if emp.employment_type_id else None,
            })

        return Response({"count": len(results), "results": results})

    def post(self, request):
        from apps.accounts.models import Employee
        from apps.master.models import ShiftCategory
        from .models import EmployeeShift

        emp_id   = request.data.get("employee")
        shift_id = request.data.get("shift")
        eff_from = request.data.get("effective_from")
        eff_to   = request.data.get("effective_to")
        job_type = request.data.get("job_type")

        if not emp_id or not shift_id or not eff_from:
            return Response(
                {"detail": "employee, shift, and effective_from are required."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            emp = Employee.objects.get(id=emp_id, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            shift = ShiftCategory.objects.get(id=shift_id)
        except ShiftCategory.DoesNotExist:
            return Response({"detail": "Shift not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            from_date = dt.datetime.strptime(eff_from, "%Y-%m-%d").date()
            to_date   = dt.datetime.strptime(eff_to, "%Y-%m-%d").date() if eff_to else None
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        es   = EmployeeShift.objects.create(
            employee=emp, shift=shift,
            effective_from=from_date, effective_to=to_date,
            job_type=job_type,
        )
        dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")

        return Response({
            "id":             str(es.id),
            "employee_id":    str(emp.id),
            "employee_name":  emp.full_name,
            "employee_code":  emp.employee_code,
            "department":     dept,
            "shift_id":       str(shift.id),
            "shift_name":     shift.name,
            "start_time":     shift.start_time.strftime("%H:%M:%S"),
            "end_time":       shift.end_time.strftime("%H:%M:%S"),
            "effective_from": es.effective_from.isoformat(),
            "effective_to":   es.effective_to.isoformat() if es.effective_to else None,
            "job_type":       es.job_type,
        }, status=status.HTTP_201_CREATED)

    def patch(self, request, pk=None):
        from apps.master.models import ShiftCategory
        from .models import EmployeeShift

        if not pk:
            return Response({"detail": "pk required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            es = EmployeeShift.objects.select_related("employee", "shift").get(id=pk, is_deleted=False)
        except EmployeeShift.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if "shift" in request.data:
            try:
                es.shift = ShiftCategory.objects.get(id=request.data["shift"])
            except ShiftCategory.DoesNotExist:
                return Response({"detail": "Shift not found."}, status=status.HTTP_404_NOT_FOUND)

        if "effective_from" in request.data:
            es.effective_from = dt.datetime.strptime(request.data["effective_from"], "%Y-%m-%d").date()
        if "effective_to" in request.data:
            val = request.data["effective_to"]
            es.effective_to = dt.datetime.strptime(val, "%Y-%m-%d").date() if val else None
        if "job_type" in request.data:
            es.job_type = request.data["job_type"] or None

        es.save()

        emp  = es.employee
        dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")

        return Response({
            "id":             str(es.id),
            "employee_id":    str(emp.id),
            "employee_name":  emp.full_name,
            "employee_code":  emp.employee_code,
            "department":     dept,
            "shift_id":       str(es.shift_id),
            "shift_name":     es.shift.name,
            "start_time":     es.shift.start_time.strftime("%H:%M:%S"),
            "end_time":       es.shift.end_time.strftime("%H:%M:%S"),
            "effective_from": es.effective_from.isoformat(),
            "effective_to":   es.effective_to.isoformat() if es.effective_to else None,
            "job_type":       es.job_type,
        })
# FIND AT BOTTOM OF views.py — REPLACE WITH:
def is_clockin_allowed_for_no_shift(employee, target_date: date) -> bool:
    return AttendanceClockInEnable.objects.filter(
        employee=employee,
        date_from__lte=target_date,
        date_to__gte=target_date,
        enabled=True,
        is_deleted=False,
    ).exists()


class EmployeeScheduleView(APIView):
    """
    GET /attendance/schedule/?employee=<id>&date_from=YYYY-MM-DD&date_to=YYYY-MM-DD
    Returns per-day shift + job_type + attendance status for the date range.
    Used by the Job Type & Schedule tab in the frontend.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import Employee
        from .models import EmployeeShift

        emp_id       = request.query_params.get("employee")
        date_from_str = request.query_params.get("date_from")
        date_to_str   = request.query_params.get("date_to")

        if not emp_id:
            return Response({"detail": "employee is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emp = Employee.objects.get(id=emp_id, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        today = date.today()
        try:
            date_from = dt.datetime.strptime(date_from_str, "%Y-%m-%d").date() if date_from_str else today.replace(day=1)
            date_to   = dt.datetime.strptime(date_to_str,   "%Y-%m-%d").date() if date_to_str   else today
        except ValueError:
            return Response({"detail": "Invalid date format. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        # Fetch all shift assignments that overlap the requested range
        shifts = EmployeeShift.objects.filter(
            employee=emp,
            is_deleted=False,
            effective_from__lte=date_to,
        ).filter(
            account_models.Q(effective_to__isnull=True) | models.Q(effective_to__gte=date_from)
        ).select_related("shift").order_by("effective_from")

        # Attendance records for the range
        att_map = {
            r.date: r
            for r in AttendanceRecord.objects.filter(
                employee=emp,
                date__gte=date_from,
                date__lte=date_to,
                is_deleted=False,
            )
        }

        def shift_for_date(d):
            """Return the EmployeeShift active on date d, or None."""
            for es in reversed(shifts):  # most recent first
                if es.effective_from <= d:
                    if es.effective_to is None or es.effective_to >= d:
                        return es
            return None

        results = []
        cur = date_from
        while cur <= date_to:
            es  = shift_for_date(cur)
            rec = att_map.get(cur)

            results.append({
                "date":             cur.isoformat(),
                "shift_id":         str(es.shift_id)        if es else None,
                "shift_name":       es.shift.name           if es else None,
                "check_in":         es.shift.start_time.strftime("%H:%M") if es else None,
                "check_out":        es.shift.end_time.strftime("%H:%M")   if es else None,
                "job_type":         es.job_type             if es else None,
                "employment_type":  getattr(emp, "employment_type", None),
                "status":           rec.status              if rec else None,
            })
            cur += dt.timedelta(days=1)

        return Response({"count": len(results), "results": results})


class EmployeeMonthlySummaryView(APIView):
    """
    HR/Admin: monthly leave + attendance summary for an employee.
    GET /attendance/employee-summary/?employee=<id>&year=YYYY&month=MM
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import Employee

        emp_id = request.query_params.get("employee")
        if not emp_id:
            return Response({"detail": "employee is required."}, status=status.HTTP_400_BAD_REQUEST)

        is_hr    = request.user.is_staff or getattr(request.user, "is_superuser", False)
        hr_perms = getattr(request, "user_permissions", [])
        can_view = (
            is_hr
            or "pmt.hrms.attendance.view" in hr_perms
            or "pmt.hrms.leave.manage" in hr_perms
        )
        if not can_view and str(request.user.id) != emp_id:
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        today = date.today()
        try:
            year  = int(request.query_params.get("year",  today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError:
            return Response({"detail": "Invalid year/month."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emp = Employee.objects.get(id=emp_id, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        # ── Attendance counts for the selected month ──
        records = AttendanceRecord.objects.filter(
            employee=emp, date__year=year, date__month=month, is_deleted=False
        )
        present  = records.filter(status=AttendanceStatus.PRESENT).count()
        wfh      = records.filter(status=AttendanceStatus.WFH).count()
        half_day = records.filter(status=AttendanceStatus.HALF_DAY).count()
        on_leave = records.filter(status=AttendanceStatus.ON_LEAVE).count()
        absent   = records.filter(status=AttendanceStatus.ABSENT).count()

        attendance = {
            "present":  present,
            "on_site":  present,   # "on-site" = days marked Present (non-remote)
            "wfh":      wfh,
            "half_day": half_day,
            "on_leave": on_leave,
            "absent":   absent,
        }

        # ── Leave balances (yearly totals) + used within the selected month ──
        _, last_day = calendar.monthrange(year, month)
        month_start = date(year, month, 1)
        month_end   = date(year, month, last_day)

        balances = LeaveBalance.objects.filter(employee=emp, year=year).select_related("leave_type")
        leave_data = []
        for b in balances:
            used_this_month = LeaveRequest.objects.filter(
                employee=emp, leave_type=b.leave_type,
                status=LeaveRequestStatus.APPROVED,
                start_date__lte=month_end, end_date__gte=month_start,
                is_deleted=False,
            ).aggregate(t=Sum("days_count"))["t"] or 0

            leave_data.append({
                "leave_type_id":    str(b.leave_type_id),
                "leave_type_name":  b.leave_type.name,
                "leave_type_code":  b.leave_type.code,
                "leave_type_color": b.leave_type.color,
                "total_days":       float(b.total_days),
                "used_days":        float(b.used_days),       # year-to-date used
                "remaining_days":   b.remaining_days,
                "used_this_month":  float(used_this_month),
            })

        return Response({
            "employee_id":   str(emp.id),
            "employee_name": emp.full_name,
            "employee_code": emp.employee_code,
            "year":  year,
            "month": month,
            "attendance":     attendance,
            "leave_balances": leave_data,
        })


class WFHSettingView(APIView):
    """
    GET  /attendance/wfh-settings/?department=&page_size=500
    POST /attendance/wfh-settings/  { employee, wfh_enabled }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from apps.accounts.models import Employee
        from django.db.models import Q

        dept = request.query_params.get("department", "").strip()

        emp_qs = Employee.objects.filter(
            is_active=True, is_deleted=False,
        ).select_related("department_ref", "wfh_setting", "wfh_setting__updated_by")

        if dept:
            emp_qs = emp_qs.filter(
                Q(department_ref__name__iexact=dept) |
                Q(department__iexact=dept)
            )

        try:
            page_size = min(int(request.query_params.get("page_size", 100)), 1000)
        except ValueError:
            page_size = 100

        results = []
        for emp in emp_qs[:page_size]:
            dept_name = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")
            setting   = getattr(emp, "wfh_setting", None)
            results.append({
                "id":            str(setting.id)              if setting else None,
                "employee_id":   str(emp.id),
                "employee_name": emp.full_name,
                "employee_code": emp.employee_code,
                "department":    dept_name,
                "wfh_enabled":   setting.wfh_enabled          if setting else False,
                "updated_by":    setting.updated_by.full_name if (setting and setting.updated_by_id) else None,
            })

        return Response({"count": len(results), "results": results})

    def post(self, request):
        from apps.accounts.models import Employee

        emp_id      = request.data.get("employee")
        wfh_enabled = request.data.get("wfh_enabled", False)

        if not emp_id:
            return Response({"detail": "employee is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emp = Employee.objects.get(id=emp_id, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        setting, _ = WFHSetting.objects.update_or_create(
            employee=emp,
            defaults={"wfh_enabled": bool(wfh_enabled), "updated_by": request.user},
        )

        dept_name = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")
        return Response({
            "id":            str(setting.id),
            "employee_id":   str(emp.id),
            "employee_name": emp.full_name,
            "employee_code": emp.employee_code,
            "department":    dept_name,
            "wfh_enabled":   setting.wfh_enabled,
            "updated_by":    request.user.full_name,
        })


class WFHRequestView(APIView):
    """
    Employee: GET/POST their own WFH requests.
    GET  /attendance/wfh-requests/
    POST /attendance/wfh-requests/  { requested_date, reason }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WFHRequest.objects.filter(
            employee=request.user, is_deleted=False
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = []
        for r in qs:
            results.append({
                "id":             str(r.id),
                "employee_id":    str(r.employee_id),
                "employee_name":  r.employee.full_name,
                "employee_code":  r.employee.employee_code,
                "department":     r.employee.department_ref.name if getattr(r.employee, "department_ref_id", None) else "",
                "requested_date": r.requested_date.isoformat(),
                "reason":         r.reason,
                "status":         r.status,
                "rejection_note": r.rejection_note,
                "created_at":     r.created_at.isoformat(),
            })

        return Response({"count": len(results), "results": results, "pending_count": sum(1 for r in results if r["status"] == "PENDING")})

    def post(self, request):
        requested_date = request.data.get("requested_date")
        reason         = request.data.get("reason", "")

        if not requested_date:
            return Response({"detail": "requested_date is required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            req_date = dt.datetime.strptime(requested_date, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)

        if req_date <= date.today():
            return Response({"detail": "WFH requests must be for a future date."}, status=status.HTTP_400_BAD_REQUEST)

        # Check WFH is enabled for this employee
        setting = getattr(request.user, "wfh_setting", None)
        if not setting or not setting.wfh_enabled:
            return Response(
                {"detail": "WFH requests are not enabled for your account. Contact HR."},
                status=status.HTTP_403_FORBIDDEN,
            )

        r, created = WFHRequest.objects.get_or_create(
            employee=request.user,
            requested_date=req_date,
            defaults={"reason": reason, "status": "PENDING"},
        )
        if not created:
            return Response({"detail": "A WFH request already exists for this date."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({
            "id":             str(r.id),
            "requested_date": r.requested_date.isoformat(),
            "reason":         r.reason,
            "status":         r.status,
            "created_at":     r.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class WFHRequestAdminView(APIView):
    """
    HR: GET all WFH requests + approve/reject.
    GET /attendance/wfh-requests/admin/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = WFHRequest.objects.filter(is_deleted=False).select_related(
            "employee", "employee__department_ref", "reviewed_by"
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = []
        for r in qs:
            results.append({
                "id":             str(r.id),
                "employee_id":    str(r.employee_id),
                "employee_name":  r.employee.full_name,
                "employee_code":  r.employee.employee_code,
                "department":     r.employee.department_ref.name if getattr(r.employee, "department_ref_id", None) else "",
                "requested_date": r.requested_date.isoformat(),
                "reason":         r.reason,
                "status":         r.status,
                "rejection_note": r.rejection_note,
                "created_at":     r.created_at.isoformat(),
            })

        pending_count = WFHRequest.objects.filter(status="PENDING", is_deleted=False).count()
        return Response({"count": len(results), "results": results, "pending_count": pending_count})


class WFHRequestReviewView(APIView):
    """
    HR: POST /attendance/wfh-requests/<id>/review/  { action: APPROVE|REJECT, rejection_note }
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            r = WFHRequest.objects.get(id=pk, is_deleted=False)
        except WFHRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        if action not in ("APPROVE", "REJECT"):
            return Response({"detail": "action must be APPROVE or REJECT."}, status=status.HTTP_400_BAD_REQUEST)

        r.status         = "APPROVED" if action == "APPROVE" else "REJECTED"
        r.reviewed_by    = request.user
        r.rejection_note = request.data.get("rejection_note", "")
        r.save(update_fields=["status", "reviewed_by", "rejection_note"])

        return Response({"id": str(r.id), "status": r.status})


class ShiftChangeRequestView(APIView):
    """
    Employee: GET/POST their shift change requests.
    GET  /attendance/shift-change-requests/
    POST /attendance/shift-change-requests/  { request_type, requested_date, requested_shift, reason }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ShiftChangeRequest.objects.filter(
            employee=request.user, is_deleted=False
        ).select_related("requested_shift").order_by("-created_at")

        results = []
        for r in qs:
            results.append({
                "id":              str(r.id),
                "request_type":    r.request_type,
                "requested_date":  r.requested_date.isoformat() if r.requested_date else None,
                "shift_name":      r.requested_shift.name,
                "shift_id":        str(r.requested_shift_id),
                "reason":          r.reason,
                "status":          r.status,
                "rejection_note":  r.rejection_note,
                "created_at":      r.created_at.isoformat(),
            })

        return Response({"count": len(results), "results": results})

    def post(self, request):
        request_type   = request.data.get("request_type", "ONE_TIME")
        
        # ← Frontend sends TEMPORARY, backend uses ONE_TIME
        if request_type == "TEMPORARY":
            request_type = "ONE_TIME"
        
        requested_date = request.data.get("requested_date")
        shift_id       = request.data.get("requested_shift")
        reason         = request.data.get("reason", "")
        # ... rest unchanged

        if not shift_id:
            return Response({"detail": "requested_shift is required."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.master.models import ShiftCategory
        try:
            shift = ShiftCategory.objects.get(id=shift_id)
        except ShiftCategory.DoesNotExist:
            return Response({"detail": "Shift not found."}, status=status.HTTP_404_NOT_FOUND)

        req_date = None
        if request_type == "ONE_TIME":
            if not requested_date:
                return Response({"detail": "requested_date is required for ONE_TIME requests."}, status=status.HTTP_400_BAD_REQUEST)
            try:
                req_date = dt.datetime.strptime(requested_date, "%Y-%m-%d").date()
            except ValueError:
                return Response({"detail": "Invalid date format."}, status=status.HTTP_400_BAD_REQUEST)

        r = ShiftChangeRequest.objects.create(
            employee=request.user,
            request_type=request_type,
            requested_date=req_date,
            requested_shift=shift,
            reason=reason,
            status="PENDING",
        )

        return Response({
            "id":             str(r.id),
            "request_type":   r.request_type,
            "requested_date": r.requested_date.isoformat() if r.requested_date else None,
            "shift_name":     shift.name,
            "status":         r.status,
            "created_at":     r.created_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class ShiftChangeRequestAdminView(APIView):
    """
    HR: GET all shift change requests.
    GET /attendance/shift-change-requests/admin/
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        qs = ShiftChangeRequest.objects.filter(is_deleted=False).select_related(
            "employee", "requested_shift", "reviewed_by"
        ).order_by("-created_at")

        status_filter = request.query_params.get("status")
        if status_filter:
            qs = qs.filter(status=status_filter)

        results = []
        for r in qs:
            results.append({
                "id":             str(r.id),
                "employee_id":    str(r.employee_id),
                "employee_name":  r.employee.full_name,
                "employee_code":  r.employee.employee_code,
                "request_type":   r.request_type,
                "requested_date": r.requested_date.isoformat() if r.requested_date else None,
                "shift_name":     r.requested_shift.name,
                "shift_id":       str(r.requested_shift_id),
                "reason":         r.reason,
                "status":         r.status,
                "rejection_note": r.rejection_note,
                "created_at":     r.created_at.isoformat(),
            })

        pending_count = ShiftChangeRequest.objects.filter(status="PENDING", is_deleted=False).count()
        return Response({"count": len(results), "results": results, "pending_count": pending_count})


class ShiftChangeRequestReviewView(APIView):
    """
    HR: POST /attendance/shift-change-requests/<id>/review/
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            r = ShiftChangeRequest.objects.get(id=pk, is_deleted=False)
        except ShiftChangeRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        if action not in ("APPROVE", "REJECT"):
            return Response({"detail": "action must be APPROVE or REJECT."}, status=status.HTTP_400_BAD_REQUEST)

        r.status         = "APPROVED" if action == "APPROVE" else "REJECTED"
        r.reviewed_by    = request.user
        r.rejection_note = request.data.get("rejection_note", "")
        r.save(update_fields=["status", "reviewed_by", "rejection_note"])

        # If approved and PERMANENT, update the employee's active shift assignment
        if r.status == "APPROVED" and r.request_type == "PERMANENT":
            from .models import EmployeeShift
            EmployeeShift.objects.filter(
                employee=r.employee, effective_to__isnull=True, is_deleted=False
            ).update(effective_to=date.today())
            EmployeeShift.objects.create(
                employee=r.employee,
                shift=r.requested_shift,
                effective_from=date.today(),
                effective_to=None,
            )

        return Response({"id": str(r.id), "status": r.status})


# ── Monthly Attendance Report Workflow ────────────────────────────────────────
# Flow: Reporting Manager (PM/is_manager) submits team attendance → CEO reviews
#       CEO approves or rejects → PM sees rejection with CEO's remarks

class AttendanceMonthlyReportView(APIView):
    """
    GET  /attendance/monthly-report/?year=YYYY&month=MM
         Returns current report for that month (PM sees their own, CEO sees all).

    POST /attendance/monthly-report/
         Reporting Manager submits the monthly attendance report to the CEO.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import AttendanceMonthlyReport
        year  = request.query_params.get("year",  date.today().year)
        month = request.query_params.get("month", date.today().month)
        try:
            year, month = int(year), int(month)
        except ValueError:
            return Response({"detail": "Invalid year/month."}, status=status.HTTP_400_BAD_REQUEST)

        is_ceo = getattr(request.user, "is_superuser", False)
        try:
            if is_ceo:
                report = AttendanceMonthlyReport.objects.get(year=year, month=month, is_deleted=False)
            else:
                # PM sees only their own submission
                report = AttendanceMonthlyReport.objects.get(
                    year=year, month=month, is_deleted=False,
                    reporting_manager=request.user,
                )
            return Response(_report_dict(report))
        except AttendanceMonthlyReport.DoesNotExist:
            return Response(None, status=status.HTTP_200_OK)

    def post(self, request):
        from .models import AttendanceMonthlyReport, AttendanceReportStatus
        from apps.projects.models import Project

        reporting_map = get_reporting_hierarchy_map(request.user)
        team_ids = list(reporting_map.keys())
        has_team = len(team_ids) > 0
        is_pm = Project.objects.filter(manager=request.user, is_deleted=False).exists()

        is_allowed = (
            getattr(request.user, "is_manager", False)
            or getattr(request.user, "is_pmo", False)
            or getattr(request.user, "is_staff", False)
            or has_team
            or is_pm
        )
        if not is_allowed:
            return Response({"detail": "Only reporting managers can submit attendance reports."}, status=status.HTTP_403_FORBIDDEN)

        year  = request.data.get("year",  date.today().year)
        month = request.data.get("month", date.today().month)
        try:
            year, month = int(year), int(month)
        except (ValueError, TypeError):
            return Response({"detail": "Invalid year/month."}, status=status.HTTP_400_BAD_REQUEST)

        # Each PM can submit once per month
        if AttendanceMonthlyReport.objects.filter(year=year, month=month, reporting_manager=request.user, is_deleted=False).exists():
            return Response({"detail": "You have already submitted the report for this month."}, status=status.HTTP_400_BAD_REQUEST)

        # Build summary
        if team_ids:
            records = AttendanceRecord.objects.filter(
                employee_id__in=team_ids,
                date__year=year, date__month=month, is_deleted=False
            )
            total_count = len(team_ids)
        else:
            all_emp_ids = list(
                Employee.objects.filter(is_active=True, is_deleted=False)
                .exclude(is_superuser=True)
                .values_list("id", flat=True)
            )
            records = AttendanceRecord.objects.filter(
                employee_id__in=all_emp_ids,
                date__year=year, date__month=month, is_deleted=False
            )
            total_count = len(all_emp_ids)

        summary = {
            "total_team":   total_count,
            "present":      records.filter(status=AttendanceStatus.PRESENT).count(),
            "absent":       records.filter(status=AttendanceStatus.ABSENT).count(),
            "wfh":          records.filter(status=AttendanceStatus.WFH).count(),
            "half_day":     records.filter(status=AttendanceStatus.HALF_DAY).count(),
            "on_leave":     records.filter(status=AttendanceStatus.ON_LEAVE).count(),
            "manager_name": request.user.full_name,
        }

        report = AttendanceMonthlyReport.objects.create(
            year=year,
            month=month,
            reporting_manager=request.user,
            status=AttendanceReportStatus.PENDING,
            summary_data=summary,
        )

        # Notify the CEO (superuser)
        try:
            from apps.notifications.publisher import publish_event
            from apps.notifications.constants import EventType, ReferenceType
            import calendar as _cal
            ceo_ids = list(
                Employee.objects.filter(is_superuser=True, is_active=True, is_deleted=False)
                .exclude(id=request.user.pk)
                .values_list("id", flat=True)
            )
            if ceo_ids:
                publish_event(
                    event_type=EventType.TIMESHEET_SUBMITTED,
                    reference_type=ReferenceType.EMPLOYEE,
                    reference_id=str(report.id),
                    payload={
                        "title": f"Team Attendance Report – {_cal.month_name[month]} {year}",
                        "message": (
                            f"{request.user.full_name} has submitted the team attendance report "
                            f"for {_cal.month_name[month]} {year}. Please review and approve."
                        ),
                    },
                    actor_id=str(request.user.pk),
                    recipient_ids=[str(cid) for cid in ceo_ids],
                    async_delivery=True,
                )
        except Exception:
            pass

        return Response(_report_dict(report), status=status.HTTP_201_CREATED)


class AttendanceMonthlyReportReviewView(APIView):
    """
    POST /attendance/monthly-report/<id>/review/
    CEO approves or rejects the monthly report.
    On rejection, the reporting manager (PM) is notified with the CEO's remarks.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .models import AttendanceMonthlyReport, AttendanceReportStatus
        from apps.accounts.models import Employee

        is_ceo = getattr(request.user, "is_superuser", False)
        if not is_ceo:
            return Response({"detail": "Only the CEO can approve or reject attendance reports."}, status=status.HTTP_403_FORBIDDEN)

        try:
            report = AttendanceMonthlyReport.objects.get(id=pk, is_deleted=False)
        except AttendanceMonthlyReport.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        if action not in ("APPROVE", "REJECT"):
            return Response({"detail": "action must be APPROVE or REJECT."}, status=status.HTTP_400_BAD_REQUEST)

        if report.status != AttendanceReportStatus.PENDING:
            return Response({"detail": "Report is not pending review."}, status=status.HTTP_400_BAD_REQUEST)

        report.status      = AttendanceReportStatus.APPROVED_BY_CEO if action == "APPROVE" else AttendanceReportStatus.REJECTED_BY_CEO
        report.reviewed_by = request.user
        report.ceo_remarks = request.data.get("ceo_remarks", "")
        report.save(update_fields=["status", "reviewed_by", "ceo_remarks"])

        # Notify the Reporting Manager of the decision
        try:
            from apps.notifications.publisher import publish_event
            from apps.notifications.constants import EventType, ReferenceType
            import calendar as _cal
            if report.reporting_manager_id:
                approved = report.status == AttendanceReportStatus.APPROVED_BY_CEO
                msg = (
                    f"Your {_cal.month_name[report.month]} {report.year} attendance report has been "
                    f"{'approved' if approved else 'rejected'} by the CEO."
                )
                if not approved and report.ceo_remarks:
                    msg += f" Remarks: {report.ceo_remarks}"
                publish_event(
                    event_type=EventType.TIMESHEET_APPROVED if approved else EventType.TIMESHEET_REJECTED,
                    reference_type=ReferenceType.EMPLOYEE,
                    reference_id=str(report.id),
                    payload={
                        "title": f"Attendance Report {'Approved' if approved else 'Rejected'} – {_cal.month_name[report.month]} {report.year}",
                        "message": msg,
                    },
                    actor_id=str(request.user.pk),
                    recipient_ids=[str(report.reporting_manager_id)],
                    async_delivery=True,
                )
        except Exception:
            pass

        return Response(_report_dict(report))


class AttendanceMonthlyReportListView(APIView):
    """
    GET /attendance/monthly-report/list/
    CEO: all reports.  PM: only their submissions.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import AttendanceMonthlyReport
        is_ceo = getattr(request.user, "is_superuser", False)
        qs = AttendanceMonthlyReport.objects.filter(is_deleted=False).order_by("-year", "-month")[:24]
        if not is_ceo:
            qs = qs.filter(reporting_manager=request.user)
        return Response([_report_dict(r) for r in qs])


def _report_dict(report):
    import calendar as _cal
    return {
        "id":                str(report.id),
        "year":              report.year,
        "month":             report.month,
        "month_label":       f"{_cal.month_name[report.month]} {report.year}",
        "status":            report.status,
        "status_label":      report.get_status_display(),
        "ceo_remarks":       report.ceo_remarks,
        "summary_data":      report.summary_data,
        "reporting_manager": report.reporting_manager.full_name if report.reporting_manager_id else None,
        "reviewed_by":       report.reviewed_by.full_name       if report.reviewed_by_id       else None,
        "created_at":        report.created_at.isoformat()      if report.created_at           else None,
    }



# ── Attendance Regularization Requests ────────────────────────────────────────

def _reg_dict(r):
    return {
        "id":               str(r.id),
        "employee_id":      str(r.employee_id),
        "employee_name":    r.employee.full_name if r.employee_id else "",
        "employee_code":    r.employee.employee_code if r.employee_id else "",
        "date":             str(r.date),
        "reason":           r.reason,
        "reason_label":     r.get_reason_display(),
        "requested_status": r.requested_status,
        "check_in":         r.check_in.strftime("%H:%M") if r.check_in else None,
        "check_out":        r.check_out.strftime("%H:%M") if r.check_out else None,
        "remarks":          r.remarks,
        "status":           r.status,
        "reviewer_remarks": r.reviewer_remarks,
        "reviewed_by":      r.reviewed_by.full_name if r.reviewed_by_id else None,
        "created_at":       r.created_at.isoformat() if r.created_at else None,
    }


class AttendanceRegularizationView(APIView):
    """
    GET  /attendance/regularization/        – Employee: my requests.
    POST /attendance/regularization/        – Employee: raise a new request.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import AttendanceRegularizationRequest
        qs = AttendanceRegularizationRequest.objects.filter(
            employee=request.user, is_deleted=False
        ).select_related("employee", "reviewed_by").order_by("-created_at")[:50]
        return Response([_reg_dict(r) for r in qs])

    def post(self, request):
        from .models import AttendanceRegularizationRequest, RegularizationReason, AttendanceStatus as AS

        req_date = request.data.get("date")
        reason   = request.data.get("reason", RegularizationReason.FORGOT_CHECKIN)
        req_stat = request.data.get("requested_status", AS.PRESENT)

        if not req_date:
            return Response({"detail": "date is required."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate
        valid_reasons  = [c[0] for c in RegularizationReason.choices]
        valid_statuses = [c[0] for c in AS.choices]
        if reason not in valid_reasons:
            return Response({"detail": "Invalid reason."}, status=status.HTTP_400_BAD_REQUEST)
        if req_stat not in valid_statuses:
            return Response({"detail": "Invalid requested_status."}, status=status.HTTP_400_BAD_REQUEST)

        # Parse times
        def parse_time(val):
            if not val:
                return None
            import datetime as _dt
            for fmt in ("%H:%M:%S", "%H:%M"):
                try:
                    return _dt.datetime.strptime(val, fmt).time()
                except ValueError:
                    pass
            return None

        reg = AttendanceRegularizationRequest.objects.create(
            employee         = request.user,
            date             = req_date,
            reason           = reason,
            requested_status = req_stat,
            check_in         = parse_time(request.data.get("check_in")),
            check_out        = parse_time(request.data.get("check_out")),
            remarks          = request.data.get("remarks", ""),
            status           = "PENDING",
        )

        # Notify all PMs
        try:
            from apps.notifications.publisher import publish_event
            from apps.notifications.constants import EventType, ReferenceType
            from apps.accounts.models import Employee
            pm_ids = list(
                Employee.objects.filter(is_manager=True, is_active=True, is_deleted=False)
                .exclude(id=request.user.pk)
                .values_list("id", flat=True)
            )
            if pm_ids:
                publish_event(
                    event_type=EventType.TIMESHEET_SUBMITTED,
                    reference_type=ReferenceType.EMPLOYEE,
                    reference_id=str(reg.id),
                    payload={
                        "title": f"Attendance Regularization – {request.user.full_name}",
                        "message": (
                            f"{request.user.full_name} has requested attendance regularization "
                            f"for {req_date} ({reg.get_reason_display()})."
                        ),
                    },
                    actor_id=str(request.user.pk),
                    recipient_ids=[str(pid) for pid in pm_ids],
                    async_delivery=True,
                )
        except Exception:
            pass

        return Response(_reg_dict(reg), status=status.HTTP_201_CREATED)


class AttendanceRegularizationAdminView(APIView):
    """
    GET /attendance/regularization/admin/
    PM / HR: list all regularization requests.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        from .models import AttendanceRegularizationRequest

        req_status = request.query_params.get("status", "")
        qs = AttendanceRegularizationRequest.objects.filter(
            is_deleted=False
        ).select_related("employee", "reviewed_by").order_by("-created_at")[:200]
        if req_status:
            qs = qs.filter(status=req_status)
        pending_count = AttendanceRegularizationRequest.objects.filter(status="PENDING", is_deleted=False).count()
        return Response({"count": qs.count(), "results": [_reg_dict(r) for r in qs], "pending_count": pending_count})


class AttendanceRegularizationReviewView(APIView):
    """
    POST /attendance/regularization/<id>/review/
    PM approves or rejects a regularization request.
    On approval, the attendance record is auto-created/updated.
    """
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        from .models import AttendanceRegularizationRequest

        try:
            reg = AttendanceRegularizationRequest.objects.get(id=pk, is_deleted=False)
        except AttendanceRegularizationRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        action = request.data.get("action")
        if action not in ("APPROVE", "REJECT"):
            return Response({"detail": "action must be APPROVE or REJECT."}, status=status.HTTP_400_BAD_REQUEST)

        if reg.status != "PENDING":
            return Response({"detail": "Request is not pending."}, status=status.HTTP_400_BAD_REQUEST)

        reg.status           = "APPROVED" if action == "APPROVE" else "REJECTED"
        reg.reviewed_by      = request.user
        reg.reviewer_remarks = request.data.get("reviewer_remarks", "")
        reg.save(update_fields=["status", "reviewed_by", "reviewer_remarks"])

        if reg.status == "APPROVED":
            # Auto-create or update the AttendanceRecord
            record, created = AttendanceRecord.objects.get_or_create(
                employee=reg.employee,
                date=reg.date,
                defaults={
                    "status":    reg.requested_status,
                    "check_in":  reg.check_in,
                    "check_out": reg.check_out,
                    "notes":     f"Regularized by {request.user.full_name} via request.",
                },
            )
            if not created:
                # Update existing record
                if reg.check_in:
                    record.check_in  = reg.check_in
                if reg.check_out:
                    record.check_out = reg.check_out
                record.status = reg.requested_status
                record.notes  = (record.notes or "") + f"\nRegularized by {request.user.full_name}."
                record.save(update_fields=["check_in", "check_out", "status", "notes"])

        return Response(_reg_dict(reg))