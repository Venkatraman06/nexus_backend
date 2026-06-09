from django.db import models

from apps.common.models import BaseModel
from packages.workflow.field import StateField


class FollowUpType(models.TextChoices):
    EMAIL      = "EMAIL",      "Email"
    CALL       = "CALL",       "Call"
    MEETING    = "MEETING",    "Meeting"
    WHATSAPP   = "WHATSAPP",   "WhatsApp"
    SITE_VISIT = "SITE_VISIT", "Site Visit"


class FollowUpPriority(models.TextChoices):
    IMPORTANT = "IMPORTANT", "Important"
    HIGH      = "HIGH",      "High"
    MEDIUM    = "MEDIUM",    "Medium"
    LOW       = "LOW",       "Low"


class FollowUp(BaseModel):
    title = models.CharField(max_length=300)
    type = models.CharField(
        max_length=20, choices=FollowUpType.choices, default=FollowUpType.CALL
    )
    priority = models.CharField(
        max_length=20,
        choices=FollowUpPriority.choices,
        default=FollowUpPriority.MEDIUM,
    )
    description = models.TextField(blank=True, default="")
    comments = models.TextField(blank=True, default="")
    assignee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_followups",
    )
    reporter = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reported_followups",
    )
    due_date = models.DateField(null=True, blank=True)
    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)
    workflow_state = StateField(related_name="followups")

    class Meta:
        db_table = "crm_followup"
        ordering = ["-created_at"]

    def __str__(self):
        return self.title
