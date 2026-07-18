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
        if self.allocation_percentage <= 0 or self.allocation_percentage > 100:
            raise ValidationError("Allocation must be between 1% and 100%.")
        if self.end_date and self.end_date < self.start_date:
            raise ValidationError("End date cannot be before start date.")

        # Overlap check: total allocation for the employee during this period
        overlapping = Allocation.objects.filter(
            employee=self.employee,
            is_deleted=False,
            start_date__lte=self.end_date or "2099-12-31",
        )
        if self.end_date:
            overlapping = overlapping.filter(end_date__gte=self.start_date) | \
                          overlapping.filter(end_date__isnull=True)
        else:
            overlapping = overlapping.filter(end_date__isnull=True) | \
                          overlapping.filter(end_date__gte=self.start_date)

        if self.pk:
            overlapping = overlapping.exclude(pk=self.pk)

        existing_total = sum(float(a.allocation_percentage) for a in overlapping)
        if existing_total + float(self.allocation_percentage) > 100:
            raise ValidationError(
                f"Employee is over-allocated. Current total: {existing_total}%. "
                f"Adding {self.allocation_percentage}% would exceed 100%."
            )

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
