import uuid
from datetime import datetime, date

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


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
            .filter(leave_type=self.leave_type, status=LeaveRequestStatus.PENDING)
            .aggregate(t=models.Sum("days_count"))["t"] or 0
        )

    @property
    def remaining_days(self) -> float:
        return max(0.0, float(self.total_days) - float(self.used_days))

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
            delta = (self.end_date - self.start_date).days + 1
            self.days_count = max(1, delta)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} | {self.leave_type.name} | {self.start_date} – {self.end_date}"


import uuid
from datetime import datetime, date

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


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
            .filter(leave_type=self.leave_type, status=LeaveRequestStatus.PENDING)
            .aggregate(t=models.Sum("days_count"))["t"] or 0
        )

    @property
    def remaining_days(self) -> float:
        return max(0.0, float(self.total_days) - float(self.used_days))

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
            delta = (self.end_date - self.start_date).days + 1
            self.days_count = max(1, delta)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} | {self.leave_type.name} | {self.start_date} – {self.end_date}"


# ── NEW: HR-granted clock-in permission for no-shift employees ────────────────

class AttendanceClockInEnable(BaseModel):
    """
    HR/Admin can grant a specific employee (who has no shift) permission
    to clock in/out on a particular date.

    The CheckInView and CheckOutView check this table when
    shift_applicable=False and the employee has no shift assigned.
    """
    employee   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="clockin_enables",
    )
    date       = models.DateField()
    enabled    = models.BooleanField(default=True)
    enabled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="clockin_enables_granted",
    )

    class Meta:
        db_table       = "hrms_attendance_clockin_enable"
        unique_together = ("employee", "date")
        ordering       = ["-date"]

    def __str__(self):
        state = "enabled" if self.enabled else "disabled"
        return f"{self.employee} | {self.date} | {state}"