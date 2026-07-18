"""
ProjectComment model — stores per-project dashboard comments with acknowledgement tracking.
"""
import uuid

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class ProjectComment(BaseModel):
    """
    A comment on a project, intended for CEO/Admin/Project Manager to communicate
    important notes to the team. Team members can acknowledge each comment.
    """
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="comments",
    )
    body = models.TextField()
    # Pinned comments appear at the top
    is_pinned = models.BooleanField(default=False)

    class Meta:
        db_table = "project_comment"
        ordering = ["-is_pinned", "-created_at"]

    def __str__(self):
        return f"[{self.project.code}] {self.body[:60]}"


class ProjectCommentAcknowledgement(models.Model):
    """
    Records a single employee's acknowledgement of a ProjectComment.
    A unique constraint prevents double-acknowledgements.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    comment = models.ForeignKey(
        ProjectComment,
        on_delete=models.CASCADE,
        related_name="acknowledgements",
    )
    acknowledged_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="comment_acknowledgements",
    )
    acknowledged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "project_comment_acknowledgement"
        unique_together = [("comment", "acknowledged_by")]
        ordering = ["acknowledged_at"]

    def __str__(self):
        return f"{self.acknowledged_by} ack comment {self.comment_id}"
