from django.core.exceptions import ValidationError
from django.db import models

from apps.common.models import BaseModel
from apps.common.constants import DAILY_HOURS


class Allocation(BaseModel):
    """
    Tracks what percentage of an employee's capacity is allocated to a project.
    Validation ensures total allocation per employee cannot exceed 100%.
    """
    employee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    allocation_percentage = models.DecimalField(
        max_digits=5, decimal_places=2,
        help_text="e.g. 50.00 means 50% = 4h/day on 8h work day",
    )
    start_date = models.DateField()
    end_date = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, default="")

    class Meta:
        db_table = "project_allocation"
        ordering = ["-start_date"]
        indexes = [
            models.Index(fields=["employee", "start_date"]),
        ]

    def __str__(self):
        return f"{self.employee} → {self.project} @ {self.allocation_percentage}%"

    @property
    def daily_hours(self):
        return (float(self.allocation_percentage) / 100) * DAILY_HOURS

    def clean(self):
        if not self.allocation_percentage or self.allocation_percentage <= 0 or self.allocation_percentage > 100:
            raise ValidationError("Allocation percentage must be between 1% and 100%.")
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

        emp_id = getattr(self, "employee_id", None) or (self.employee.id if getattr(self, "employee", None) else None)
        if not emp_id:
            return

        # Query overlapping active allocations for the same employee
        qs = Allocation.objects.filter(
            employee_id=emp_id,
            is_deleted=False,
        )
        if self.end_date:
            qs = qs.filter(
                start_date__lte=self.end_date,
            ).filter(
                models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.start_date)
            )
        else:
            qs = qs.filter(
                models.Q(end_date__isnull=True) | models.Q(end_date__gte=self.start_date)
            )

        if self.pk:
            qs = qs.exclude(pk=self.pk)

        existing_total = sum(float(a.allocation_percentage or 0) for a in qs)
        alloc_pct = float(self.allocation_percentage or 0)
        total = existing_total + alloc_pct
        if total > 100.01:
            raise ValidationError(
                f"Employee is over-allocated for this period. Current active allocation: {existing_total:.0f}%. "
                f"Adding {alloc_pct:.0f}% would total {total:.0f}%, exceeding 100%."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
