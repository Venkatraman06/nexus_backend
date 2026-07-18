from django.db import models

from apps.common.constants import TimesheetStatus
from apps.common.models import BaseModel


class TimesheetConfig(BaseModel):
    """Singleton-style config for daily capacity (admin configurable)."""
    daily_capacity_hours = models.DecimalField(
        max_digits=4, decimal_places=2, default=8,
        help_text="Effective daily capacity in hours (8, 9, or 10)",
    )

    class Meta:
        db_table = "timesheet_config"

    def __str__(self):
        return f"Daily capacity: {self.daily_capacity_hours}h"

    @classmethod
    def get_daily_capacity(cls) -> float:
        row = cls.objects.filter(is_deleted=False).order_by("created_at").first()
        return float(row.daily_capacity_hours) if row else 8.0


class WeeklyTimesheet(BaseModel):
    """Weekly timesheet container — auto-generated per employee per week."""
    employee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="weekly_timesheets",
    )
    week_start = models.DateField(help_text="Sunday of the week")
    week_end = models.DateField(help_text="Saturday of the week")
    status = models.CharField(
        max_length=12,
        choices=TimesheetStatus.choices,
        default=TimesheetStatus.DRAFT,
    )
    total_hours = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    expected_hours = models.DecimalField(max_digits=7, decimal_places=2, default=40)
    submitted_at = models.DateTimeField(null=True, blank=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_timesheets",
    )
    review_comment = models.TextField(blank=True, default="")

    class Meta:
        db_table = "weekly_timesheet"
        ordering = ["-week_start"]
        unique_together = [("employee", "week_start")]
        indexes = [
            models.Index(fields=["employee", "week_start"]),
            models.Index(fields=["status", "week_start"]),
        ]

    def __str__(self):
        return f"{self.employee} | {self.week_start} | {self.status}"


class TimesheetReviewLog(BaseModel):
    """Audit trail for submit / approve / reject actions."""
    weekly_timesheet = models.ForeignKey(
        WeeklyTimesheet,
        on_delete=models.CASCADE,
        related_name="review_logs",
    )
    action = models.CharField(max_length=20)
    comment = models.TextField(blank=True, default="")
    performed_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="timesheet_review_actions",
    )

    class Meta:
        db_table = "timesheet_review_log"
        ordering = ["-created_at"]
