import uuid

from django.db import models

from apps.common.models import BaseModel


class ConversationType(models.TextChoices):
    DIRECT = "DIRECT", "Direct"
    GROUP = "GROUP", "Group"


class ParticipantRole(models.TextChoices):
    MEMBER = "MEMBER", "Member"
    ADMIN = "ADMIN", "Admin"


class Conversation(BaseModel):
    type = models.CharField(max_length=10, choices=ConversationType.choices)
    name = models.CharField(max_length=255, blank=True, default="")
    avatar = models.CharField(max_length=500, blank=True, default="")
    is_archived = models.BooleanField(default=False)
    last_message_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_conversation"
        ordering = ["-last_message_at", "-created_at"]

    def __str__(self):
        return self.name or f"Conversation {self.id}"


class ConversationParticipant(BaseModel):
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="participants",
    )
    employee = models.ForeignKey(
        "accounts.Employee", on_delete=models.CASCADE, related_name="chat_participations",
    )
    role = models.CharField(max_length=10, choices=ParticipantRole.choices, default=ParticipantRole.MEMBER)
    is_favorite = models.BooleanField(default=False)
    muted = models.BooleanField(default=False)
    # Messages live in MongoDB (apps/chat/mongo.py), not Postgres, so this can
    # only be an informational string reference — no cross-database FK.
    last_read_message_id = models.CharField(max_length=64, null=True, blank=True)
    last_read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "chat_conversation_participant"
        constraints = [
            models.UniqueConstraint(
                fields=["conversation", "employee"], name="uniq_chat_participant",
            )
        ]

    def __str__(self):
        return f"{self.employee} in {self.conversation}"


class ConversationAuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    conversation = models.ForeignKey(
        Conversation, on_delete=models.CASCADE, related_name="audit_logs",
    )
    actor = models.ForeignKey(
        "accounts.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_audit_actions",
    )
    action = models.CharField(max_length=50)
    target_employee = models.ForeignKey(
        "accounts.Employee", on_delete=models.SET_NULL, null=True, blank=True, related_name="chat_audit_targets",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "chat_conversation_audit_log"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.action} on {self.conversation_id} by {self.actor}"
