import uuid

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from .state import State
from .transition import Transition


class Proceeding(models.Model):
    """Records every state transition for any model that uses StateField."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    object_id = models.UUIDField()
    workflow_object = GenericForeignKey("content_type", "object_id")
    transition = models.ForeignKey(
        Transition,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="proceedings",
    )
    previous_state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outgoing_proceedings",
    )
    state = models.ForeignKey(
        State,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="incoming_proceedings",
    )
    comments = models.TextField(blank=True, default="")
    transitioned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.workflow_object} → {self.state}"

    class Meta:
        db_table = "master_workflow_proceeding"
        verbose_name = _("proceeding")
        verbose_name_plural = _("proceedings")
        ordering = ["-created_at"]
