from django.db import models
from django.core.exceptions import ValidationError

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
    remarks = models.TextField(blank=True, default="")
    is_billable = models.BooleanField(default=True)

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

    def clean(self):
        if self.hours <= 0:
            raise ValidationError("Hours must be greater than zero.")
        if self.hours > 24:
            raise ValidationError("Cannot log more than 24 hours per entry.")
