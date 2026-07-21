from django.db import models

from apps.common.models import BaseModel
from packages.workflow.field import StateField


class TodoPriority(models.TextChoices):
    HIGH   = "HIGH",   "High"
    MEDIUM = "MEDIUM", "Medium"
    LOW    = "LOW",    "Low"


class Todo(BaseModel):
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    content = models.TextField(blank=True, default="")
    priority = models.CharField(
        max_length=20,
        choices=TodoPriority.choices,
        default=TodoPriority.MEDIUM,
    )
    assignees = models.ManyToManyField(
        "accounts.Employee",
        blank=True,
        related_name="assigned_todos",
    )
    reporter = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reported_todos",
    )
    start_date = models.DateField(null=True, blank=True)
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    workflow_state = StateField(related_name="todos")

    class Meta:
        db_table = "workspace_todo"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
