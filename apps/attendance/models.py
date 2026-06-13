import uuid
from datetime import datetime, date

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel

import datetime as dt
class AttendanceStatus(models.TextChoices):
    PRESENT     = "PRESENT",     "Present"
    ABSENT      = "ABSENT",      "Absent"
    HALF_DAY    = "HALF_DAY",    "Half Day"
    WFH         = "WFH",         "Work From Home"
    ON_LEAVE    = "ON_LEAVE",    "On Leave"
    HOLIDAY     = "HOLIDAY",     "Holiday"
    WEEKEND     = "WEEKEND",     "Weekend"


class BreakType(models.TextChoices):
    TEA   = "TEA",   "Tea Break"
    LUNCH = "LUNCH", "Lunch Break"
    OTHER = "OTHER", "Other"


class LeaveRequestStatus(models.TextChoices):
    PENDING   = "PENDING",   "Pending"
    APPROVED  = "APPROVED",  "Approved"
    REJECTED  = "REJECTED",  "Rejected"
    CANCELLED = "CANCELLED", "Cancelled"


class AttendanceRecord(BaseModel):
    employee      = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="attendance_records",
    )
    date          = models.DateField()
    check_in      = models.TimeField(null=True, blank=True)
    check_out     = models.TimeField(null=True, blank=True)
    status        = models.CharField(max_length=20, choices=AttendanceStatus.choices, default=AttendanceStatus.PRESENT)
    notes         = models.TextField(blank=True, default="")
    check_in_lat  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_in_lng  = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_out_lat = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    check_out_lng = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)

    class Meta:
        db_table = "hrms_attendance_record"
        unique_together = ("employee", "date")
        ordering = ["-date"]

    @property
    def duration_hours(self) -> float:
        if self.check_in and self.check_out:
            ci = datetime.combine(date.today(), self.check_in)
            co = datetime.combine(date.today(), self.check_out)
            if co > ci:
                return round((co - ci).seconds / 3600, 2)
        return 0.0

    @property
    def total_break_minutes(self) -> int:
        total = 0
        for b in self.breaks.filter(is_deleted=False):
            total += b.duration_minutes
        return total

    @property
    def working_hours(self) -> float:
        gross = self.duration_hours
        if gross <= 0:
            return 0.0
        return round(max(0.0, gross - self.total_break_minutes / 60), 2)

    def __str__(self):
        return f"{self.employee} | {self.date} | {self.status}"


class AttendanceBreak(BaseModel):
    attendance = models.ForeignKey(AttendanceRecord, on_delete=models.CASCADE, related_name="breaks")
    break_type = models.CharField(max_length=20, choices=BreakType.choices, default=BreakType.OTHER)
    start_time = models.TimeField()
    end_time   = models.TimeField(null=True, blank=True)

    class Meta:
        db_table = "hrms_attendance_break"
        ordering = ["start_time"]

    @property
    def duration_minutes(self) -> int:
        if self.start_time and self.end_time:
            a = datetime.combine(date.today(), self.start_time)
            b = datetime.combine(date.today(), self.end_time)
            if b > a:
                return int((b - a).seconds / 60)
        return 0

    def __str__(self):
        return f"{self.attendance} | {self.break_type} | {self.start_time}"


class LeaveType(BaseModel):
    name     = models.CharField(max_length=60, unique=True)
    code     = models.CharField(max_length=20, unique=True)
    max_days = models.PositiveIntegerField(default=0, help_text="Max days allowed per year (0 = unlimited)")
    is_paid  = models.BooleanField(default=True)
    color    = models.CharField(max_length=20, default="#1677ff")

    class Meta:
        db_table = "hrms_leave_type"
        ordering = ["name"]

    def __str__(self):
        return self.name


class LeaveBalance(BaseModel):
    employee   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="leave_balances",
    )
    leave_type = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="balances")
    year       = models.PositiveIntegerField()
    total_days = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    used_days  = models.DecimalField(max_digits=5, decimal_places=1, default=0)

    class Meta:
        db_table = "hrms_leave_balance"
        unique_together = ("employee", "leave_type", "year")
        ordering = ["leave_type__name"]

    @property
    def pending_days(self) -> float:
        return float(
        self.employee.leave_requests
        .filter(
            leave_type=self.leave_type,
            status=LeaveRequestStatus.PENDING,
            start_date__year=self.year,
        )
        .aggregate(t=models.Sum("days_count"))["t"] or 0
    )

    @property
    def remaining_days(self) -> float:
        return max(0.0, float(self.total_days) - float(self.used_days) - self.pending_days)

    def __str__(self):
        return f"{self.employee} | {self.leave_type.name} | {self.year}"


class LeaveRequest(BaseModel):
    employee         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="leave_requests",
    )
    leave_type       = models.ForeignKey(LeaveType, on_delete=models.PROTECT, related_name="requests")
    start_date       = models.DateField()
    end_date         = models.DateField()
    days_count       = models.DecimalField(max_digits=5, decimal_places=1, default=1)
    status           = models.CharField(max_length=20, choices=LeaveRequestStatus.choices, default=LeaveRequestStatus.PENDING)
    reason           = models.TextField(blank=True, default="")
    reviewer         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="reviewed_leaves",
    )
    reviewer_remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hrms_leave_request"
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if self.start_date and self.end_date:
            from apps.master.models import Holiday
            from datetime import timedelta

            holidays = set(
                Holiday.objects.filter(
                    date__gte=self.start_date,
                    date__lte=self.end_date,
                    is_active=True,
                ).values_list("date", flat=True)
            )

            count = 0
            current = self.start_date
            while current <= self.end_date:
                if current.weekday() < 5 and current not in holidays:
                    count += 1
                current += timedelta(days=1)

            self.days_count = count

        super().save(*args, **kwargs)

class LeavePolicyRule(models.Model):
    id                 = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    leave_type         = models.ForeignKey(LeaveType, on_delete=models.CASCADE, related_name="policy_rules")
    total_days         = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    carry_forward      = models.BooleanField(default=False)
    carry_forward_limit= models.DecimalField(max_digits=5, decimal_places=1, default=0)
    applicable_to      = models.CharField(max_length=20, default="ALL")
    effective_from     = models.PositiveIntegerField()
    effective_to       = models.PositiveIntegerField(null=True, blank=True)
    loss_of_pay_after  = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    auto_allocate      = models.BooleanField(default=True)
    notes              = models.TextField(blank=True, default="")
    created_by         = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="leave_policy_rules",
    )
    created_at         = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_leave_policy_rule"
        ordering = ["leave_type__name"]

    def __str__(self):
        return f"{self.leave_type.name} | {self.total_days}d | {self.effective_from}"


class LeaveMonthLock(models.Model):
    id          = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        null=True, blank=True, related_name="leave_locks",
    )
    lock_type   = models.CharField(max_length=20, default="MONTH")
    lock_reason = models.CharField(max_length=50, default="PAYROLL_PROCESSING")
    year        = models.PositiveIntegerField(null=True, blank=True)
    month       = models.PositiveIntegerField(null=True, blank=True)
    date_from   = models.DateField(null=True, blank=True)
    date_to     = models.DateField(null=True, blank=True)
    lop_days    = models.DecimalField(max_digits=5, decimal_places=1, default=0)
    lop_finalized = models.BooleanField(default=False)
    is_active   = models.BooleanField(default=True)
    notes       = models.TextField(blank=True, default="")
    locked_by   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="leave_locks_created",
    )
    created_at  = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attendance_leave_month_lock"
        ordering = ["-created_at"]

    @property
    def period_label(self):
        import calendar
        if self.lock_type == "MONTH" and self.year and self.month:
            return f"{calendar.month_name[self.month]} {self.year}"
        if self.date_from and self.date_to:
            return f"{self.date_from} to {self.date_to}"
        return "—"

    def __str__(self):
        emp = str(self.employee) if self.employee_id else "ALL"
        return f"{emp} | {self.period_label}"

class AttendanceClockInEnable(BaseModel):
    employee       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="clockin_enables",
    )
    date_from      = models.DateField()
    date_to        = models.DateField()
    enabled        = models.BooleanField(default=True)
    enabled_by     = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="clockin_enables_granted",
    )
    shift_category = models.ForeignKey(
        "master.ShiftCategory", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="clockin_enables",
    )
    job_type       = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table        = "hrms_attendance_clockin_enable"
        ordering        = ["-date_from"]

    def __str__(self):
        return f"{self.employee} | {self.date_from}–{self.date_to} | {'enabled' if self.enabled else 'disabled'}"

class EmployeeShift(BaseModel):
    employee       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="employee_shifts",
    )
    shift          = models.ForeignKey(
        "master.ShiftCategory", on_delete=models.CASCADE,
        related_name="employee_assignments",
    )
    effective_from = models.DateField()
    effective_to   = models.DateField(null=True, blank=True)
    job_type       = models.CharField(max_length=20, null=True, blank=True)

    class Meta:
        db_table = "hrms_employee_shift"
        ordering = ["-effective_from"]

    def __str__(self):
        return f"{self.employee} | {self.shift.name} | {self.effective_from}"


class WFHSetting(BaseModel):
    """HR-controlled flag: whether an employee is allowed to request WFH."""
    employee    = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="wfh_setting",
    )
    wfh_enabled = models.BooleanField(default=False)
    updated_by  = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="wfh_settings_updated",
    )

    class Meta:
        db_table = "hrms_wfh_setting"

    def __str__(self):
        return f"{self.employee} | WFH={'yes' if self.wfh_enabled else 'no'}"

class WFHRequest(BaseModel):
    """Employee requests to work from home on a specific date."""
    employee       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="wfh_requests",
    )
    requested_date = models.DateField()
    reason         = models.TextField(blank=True, default="")
    status         = models.CharField(
        max_length=20,
        choices=[("PENDING","Pending"),("APPROVED","Approved"),("REJECTED","Rejected")],
        default="PENDING",
    )
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="wfh_reviews",
    )
    rejection_note = models.TextField(blank=True, default="")

    class Meta:
        db_table        = "hrms_wfh_request"
        unique_together = ("employee", "requested_date")
        ordering        = ["-created_at"]

    def __str__(self):
        return f"{self.employee} | {self.requested_date} | {self.status}"


class ShiftChangeRequest(BaseModel):
    """Employee requests a temporary or permanent shift change."""
    REQUEST_TYPE = [("ONE_TIME", "One Time"), ("PERMANENT", "Permanent")]

    employee       = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="shift_change_requests",
    )
    request_type   = models.CharField(max_length=20, choices=REQUEST_TYPE, default="ONE_TIME")
    requested_date = models.DateField(null=True, blank=True)   # for ONE_TIME
    requested_shift = models.ForeignKey(
        "master.ShiftCategory", on_delete=models.CASCADE,
        related_name="change_requests",
    )
    reason         = models.TextField(blank=True, default="")
    status         = models.CharField(
        max_length=20,
        choices=[("PENDING","Pending"),("APPROVED","Approved"),("REJECTED","Rejected")],
        default="PENDING",
    )
    reviewed_by    = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="shift_change_reviews",
    )
    rejection_note = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hrms_shift_change_request"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} | {self.request_type} | {self.status}"