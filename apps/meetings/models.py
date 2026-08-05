from django.db import models
from apps.common.models import BaseModel
from packages.workflow.field import StateField

class MeetingMode(models.TextChoices):
    ONLINE  = "ONLINE",  "Online"
    OFFLINE = "OFFLINE", "Offline"

class MeetingPriority(models.TextChoices):
    HIGH      = "HIGH",      "High"
    MEDIUM    = "MEDIUM",    "Medium"
    LOW       = "LOW",       "Low"

class Meeting(BaseModel):
    title = models.CharField(max_length=300)
    priority = models.CharField(
        max_length=20,
        choices=MeetingPriority.choices,
        default=MeetingPriority.MEDIUM,
    )
    description = models.TextField(blank=True, default="")
    content = models.TextField(blank=True, default="")
    comments = models.TextField(blank=True, default="")
    assignees = models.ManyToManyField(
        "accounts.Employee",
        blank=True,
        related_name="assigned_meetings",
    )
    reporter = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reported_meetings",
    )
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    meeting_mode = models.CharField(
        max_length=10,
        choices=MeetingMode.choices,
        null=True, blank=True,
    )
    workflow_state = StateField(related_name="meetings")

    class Meta:
        db_table = "crm_meeting"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
