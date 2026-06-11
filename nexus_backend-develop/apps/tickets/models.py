import uuid

from django.db import models

from apps.common.models import BaseModel
from packages.storages.dynamic_storage import DynamicS3Storage
from packages.workflow.field import StateField


class TicketType(models.TextChoices):
    EPIC           = "EPIC",           "Epic"
    STORY          = "STORY",          "Story"
    TASK           = "TASK",           "Task"
    SUBTASK        = "SUBTASK",        "Sub-Task"
    BUG            = "BUG",            "Bug"
    CHANGE_REQUEST = "CHANGE_REQUEST", "Change Request"
    DEPLOYMENT     = "DEPLOYMENT",     "Deployment"
    DOCUMENT       = "DOCUMENT",       "Document"
    MILESTONE      = "MILESTONE",      "Milestone"


class TicketPriority(models.TextChoices):
    IMMEDIATE = "IMMEDIATE", "Immediate"
    CRITICAL  = "CRITICAL",  "Critical"
    HIGH      = "HIGH",      "High"
    MEDIUM    = "MEDIUM",    "Medium"
    DEFERRED  = "DEFERRED",  "Deferred"


class Ticket(BaseModel):
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="tickets",
    )
    ticket_id = models.CharField(max_length=50, unique=True, blank=True, db_index=True)
    title = models.CharField(max_length=300)
    description = models.TextField(blank=True, default="")
    type = models.CharField(
        max_length=20, choices=TicketType.choices, default=TicketType.TASK
    )
    workflow_state = StateField(related_name="tickets")
    priority = models.CharField(
        max_length=10, choices=TicketPriority.choices, default=TicketPriority.MEDIUM
    )
    parent = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="children",
    )
    assignee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="assigned_tickets",
    )
    reporter = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reported_tickets",
    )
    due_date = models.DateField(null=True, blank=True)
    original_estimate = models.DecimalField(
        max_digits=8, decimal_places=2, default=0,
        help_text="Estimated hours for this ticket",
    )
    approved = models.BooleanField(default=False)
    notify_users = models.ManyToManyField(
        "accounts.Employee",
        blank=True,
        related_name="notified_tickets",
    )

    class Meta:
        db_table = "ticket"
        ordering = ["-created_at"]

    def __str__(self):
        return f"[{self.ticket_id}] {self.title}"

    def save(self, *args, **kwargs):
        if not self.ticket_id:
            self.ticket_id = self._generate_ticket_id()
        super().save(*args, **kwargs)

    def _generate_ticket_id(self):
        prefix = self.project.code if self.project_id else "TKT"
        count = Ticket.objects.filter(project=self.project).count() + 1
        ticket_id = f"{prefix}-{count:04d}"
        while Ticket.objects.filter(ticket_id=ticket_id).exists():
            count += 1
            ticket_id = f"{prefix}-{count:04d}"
        return ticket_id

    @property
    def logged_hours(self):
        from django.db.models import Sum
        return self.work_logs.filter(is_deleted=False).aggregate(
            total=Sum("hours")
        )["total"] or 0

    @property
    def remaining_hours(self):
        return max(0, float(self.original_estimate) - float(self.logged_hours))


class TicketAttachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(
        upload_to="tickets/attachments/",
        storage=DynamicS3Storage,
    )
    file_name = models.CharField(max_length=300, blank=True, default="")
    file_size = models.PositiveBigIntegerField(default=0)
    content_type = models.CharField(max_length=100, blank=True, default="")
    uploaded_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_attachment"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return self.file_name


class TicketComment(BaseModel):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ticket_comments",
    )
    body = models.TextField()
    is_edited = models.BooleanField(default=False)

    class Meta:
        db_table = "ticket_comment"
        ordering = ["created_at"]

    def __str__(self):
        return f"Comment on {self.ticket.ticket_id} by {self.author}"


class TicketHistory(models.Model):
    """Immutable audit record of every ticket field change."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name="history")
    action = models.CharField(max_length=20, default="update")
    changes = models.JSONField(default=dict)
    changed_by = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="ticket_history_entries",
    )
    changed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ticket_history"
        ordering = ["-changed_at"]

    def __str__(self):
        return f"{self.ticket.ticket_id} [{self.action}] at {self.changed_at:%Y-%m-%d %H:%M}"
