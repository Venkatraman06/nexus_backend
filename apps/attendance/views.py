import calendar
import csv
import io
import datetime as dt
from datetime import date

from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.accounts import models as account_models
from drf_spectacular.utils import extend_schema, OpenApiResponse

from .models import (
    AttendanceRecord, AttendanceBreak, AttendanceStatus, BreakType,
    LeaveBalance, LeaveRequest, LeaveType, LeaveRequestStatus,
    AttendanceClockInEnable,
)
from .serializers import (
    AttendanceRecordSerializer, CheckInSerializer, CheckOutSerializer,
    StartBreakSerializer,
    LeaveBalanceSerializer, LeaveRequestSerializer, LeaveReviewSerializer, LeaveTypeSerializer,
)

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
    """Mark check-in for today (captures geo-location)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"], request=CheckInSerializer, responses={200: AttendanceRecordSerializer})
    def post(self, request):
        serializer = CheckInSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        today    = date.today()
        now_time = dt.datetime.now().time()
        lat      = serializer.validated_data.get("lat")
        lng      = serializer.validated_data.get("lng")
        me       = request.user

        # Allow clock-in if shift_applicable=True OR a shift is assigned
        has_shift = getattr(me, "shift_applicable", False) or bool(
            getattr(me, "shift_category_id", None) or
            (getattr(me, "custom_shift_start", None) and getattr(me, "custom_shift_end", None))
        )

        if has_shift:
            # Enforce shift window
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
            # No shift — require HR to have granted clock-in permission for today
            if not is_clockin_allowed_for_no_shift(me, today):
                return Response(
                    {"detail": "You have not been granted clock-in permission for today."},
                    status=status.HTTP_403_FORBIDDEN,
                )

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
    """Mark check-out for today (captures geo-location)."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["attendance"], request=CheckOutSerializer, responses={200: AttendanceRecordSerializer})
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

        # Allow check-out if shift_applicable=True OR a shift is assigned
        has_shift = getattr(me, "shift_applicable", False) or bool(
            getattr(me, "shift_category_id", None) or
            (getattr(me, "custom_shift_start", None) and getattr(me, "custom_shift_end", None))
        )

        if has_shift:
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
        writer = csv.writer(output)

        writer.writerow([f"Attendance Report — {month_name} {year}"])
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
        types = LeaveType.objects.filter(is_active=True, is_deleted=False)
        return Response(LeaveTypeSerializer(types, many=True).data)


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
        serializer = LeaveRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        leave = serializer.save(employee=request.user)

        from apps.notifications.constants import EventType, ReferenceType
        from apps.notifications.publisher import publish_event
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


class LeaveReviewView(APIView):
    """PMO/manager reviews a leave request."""
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["leave"], request=LeaveReviewSerializer)
    def post(self, request, pk):
        try:
            leave = LeaveRequest.objects.get(pk=pk, is_deleted=False)
        except LeaveRequest.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        if leave.status != LeaveRequestStatus.PENDING:
            return Response({"detail": "Only PENDING requests can be reviewed."}, status=status.HTTP_400_BAD_REQUEST)

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

        return Response(LeaveRequestSerializer(leave).data)

class AdminLeaveRequestListView(APIView):
    """HR / PMO view — all employees' leave requests with summary stats."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
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
            }
            for lr in qs
        ]

        return Response({"summary": summary, "results": data})


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

class AttendanceClockInEnableView(APIView):
    """
    GET  /attendance/enable-clockin/?date=YYYY-MM-DD
    POST /attendance/enable-clockin/  { employee, date, enabled }
    """
    permission_classes = [IsAuthenticated]

    def get(self, request):
        date_str = request.query_params.get("date", str(date.today()))
        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date."}, status=status.HTTP_400_BAD_REQUEST)

        entries = AttendanceClockInEnable.objects.filter(
            date=target_date, is_deleted=False
        ).select_related("employee", "enabled_by")

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
                "date":          e.date.isoformat(),
                "enabled":       e.enabled,
                "enabled_by":    e.enabled_by.full_name if e.enabled_by_id else None,
            })

        return Response({"count": len(results), "results": results})

    def post(self, request):
        from apps.accounts.models import Employee

        employee_id = request.data.get("employee")
        date_str    = request.data.get("date")
        enabled     = request.data.get("enabled", True)

        if not employee_id or not date_str:
            return Response({"detail": "employee and date are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            emp = Employee.objects.get(id=employee_id, is_deleted=False)
        except Employee.DoesNotExist:
            return Response({"detail": "Employee not found."}, status=status.HTTP_404_NOT_FOUND)

        try:
            target_date = dt.datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Invalid date. Use YYYY-MM-DD."}, status=status.HTTP_400_BAD_REQUEST)

        entry, created = AttendanceClockInEnable.objects.update_or_create(
            employee=emp,
            date=target_date,
            defaults={"enabled": bool(enabled), "enabled_by": request.user, "is_deleted": False},
        )

        dept = emp.department_ref.name if getattr(emp, "department_ref_id", None) else (emp.department or "")

        return Response(
            {
                "id":            str(entry.id),
                "employee_id":   str(emp.id),
                "employee_name": emp.full_name,
                "employee_code": emp.employee_code,
                "department":    dept,
                "date":          entry.date.isoformat(),
                "enabled":       entry.enabled,
                "enabled_by":    request.user.full_name,
                "created":       created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


def is_clockin_allowed_for_no_shift(employee, target_date: date) -> bool:
    """Returns True if a no-shift employee has been granted clock-in permission for the given date."""
    return AttendanceClockInEnable.objects.filter(
        employee=employee, date=target_date, enabled=True, is_deleted=False,
    ).exists()