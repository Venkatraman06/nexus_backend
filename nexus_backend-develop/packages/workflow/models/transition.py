import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _

from .state import State


class Transition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="workflow_transitions",
    )
    source_state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_transitions",
    )
    destination_state = models.ForeignKey(
        State,
        on_delete=models.CASCADE,
        related_name="incoming_transitions",
    )
    label = models.CharField(max_length=100, blank=True, default="")
    groups = models.ManyToManyField(
        "pmt_workflow.WorkflowGroup",
        blank=True,
        related_name="transitions",
        help_text="Groups that can execute this transition. Empty = anyone can.",
    )
    position = models.JSONField(
        default=dict,
        blank=True,
        help_text="Visual position in workflow diagram {source: {x,y}, destination: {x,y}}",
    )

    def __str__(self):
        return f"{self.source_state} → {self.destination_state}"

    class Meta:
        db_table = "master_workflow_transition"
        verbose_name = _("transition")
        verbose_name_plural = _("transitions")
        unique_together = ("content_type", "source_state", "destination_state")
        ordering = ["source_state__order", "destination_state__order"]
