from django.db import models
from django.core.exceptions import ValidationError

from apps.common.constants import WorkLogCategory
from apps.common.models import BaseModel


class WorkLog(BaseModel):
    """
    Time log entry — employees log hours against tickets.
    Kept for backward compatibility with timesheets.
    """
    employee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="work_logs",
    )
    ticket = models.ForeignKey(
        "tickets.Ticket",
        on_delete=models.CASCADE,
        related_name="work_logs",
        null=True, blank=True,
    )
    log_date = models.DateField()
    hours = models.DecimalField(max_digits=5, decimal_places=2)
    description = models.TextField(blank=True, default="", help_text="Work performed")
    remarks = models.TextField(blank=True, default="")
    category = models.CharField(
        max_length=15,
        choices=WorkLogCategory.choices,
        default=WorkLogCategory.BILLABLE,
    )
    is_billable = models.BooleanField(default=True)
    weekly_timesheet = models.ForeignKey(
        "timesheets.WeeklyTimesheet",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="work_logs",
    )

    class Meta:
        db_table = "project_work_log"
        ordering = ["-log_date"]
        indexes = [
            models.Index(fields=["log_date", "employee"]),
            models.Index(fields=["ticket", "employee"]),
        ]

    def __str__(self):
        ref = self.ticket.ticket_id if self.ticket else "—"
        return f"{self.employee} | {ref} | {self.log_date} | {self.hours}h"

    def save(self, *args, **kwargs):
        self.is_billable = self.category == WorkLogCategory.BILLABLE
        super().save(*args, **kwargs)

    def clean(self):
        if self.hours <= 0:
            raise ValidationError("Hours must be greater than zero.")
        if self.hours > 24:
            raise ValidationError("Cannot log more than 24 hours per entry.")
