import uuid

from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel
from apps.notifications.constants import (
    EventType,
    NotificationChannel,
    NotificationSeverity,
    ReferenceType,
)


class NotificationTemplate(BaseModel):
    """Reusable message templates — seeded defaults, editable via admin."""

    event_type = models.CharField(max_length=64, choices=EventType.choices, unique=True)
    title_template = models.CharField(max_length=255)
    message_template = models.TextField()
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
    )
    default_action_url = models.CharField(max_length=512, blank=True, default="")
    supported_channels = models.JSONField(default=list)

    class Meta:
        db_table = "notification_templates"
        ordering = ["event_type"]

    def __str__(self):
        return self.event_type


class NotificationEventLog(BaseModel):
    """Audit trail of published domain events (for debugging / replay)."""

    event_type = models.CharField(max_length=64, db_index=True)
    reference_type = models.CharField(max_length=32, blank=True, default="")
    reference_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    payload = models.JSONField(default=dict)
    actor = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_notification_events",
    )
    processed_at = models.DateTimeField(null=True, blank=True)
    notifications_created = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "notification_event_logs"
        ordering = ["-created_at"]


class Notification(models.Model):
    """
    In-app (and future channel) notification record.
    Never hard-deleted on read — uses is_read + read_at.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    recipient = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    event_type = models.CharField(max_length=64, choices=EventType.choices, db_index=True)
    title = models.CharField(max_length=255)
    message = models.TextField()
    reference_type = models.CharField(
        max_length=32,
        choices=ReferenceType.choices,
        blank=True,
        default="",
    )
    reference_id = models.CharField(max_length=64, blank=True, default="", db_index=True)
    action_url = models.CharField(max_length=512, blank=True, default="")
    severity = models.CharField(
        max_length=16,
        choices=NotificationSeverity.choices,
        default=NotificationSeverity.INFO,
    )
    channel = models.CharField(
        max_length=16,
        choices=NotificationChannel.choices,
        default=NotificationChannel.IN_APP,
    )
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    dedup_key = models.CharField(max_length=255, blank=True, default="", db_index=True)
    metadata = models.JSONField(default=dict, blank=True)
    actor = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_notifications",
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "notifications"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["recipient", "is_read", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["recipient", "dedup_key"],
                condition=~models.Q(dedup_key=""),
                name="unique_notification_dedup_per_recipient",
            ),
        ]

    def mark_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=["is_read", "read_at"])

    def __str__(self):
        return f"{self.event_type} → {self.recipient_id}"
