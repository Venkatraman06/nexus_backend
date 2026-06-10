from django.db import models

from apps.common.models import BaseModel
from packages.workflow.field import StateField


class SocialPost(BaseModel):
    title = models.CharField(max_length=300)
    content = models.TextField(blank=True, default="")
    image = models.ImageField(
        upload_to="social_feed/images/",
        null=True, blank=True,
    )
    attachment = models.FileField(
        upload_to="social_feed/attachments/",
        null=True, blank=True,
    )
    created_by_name = models.CharField(max_length=200, blank=True, default="")
    is_company_wide = models.BooleanField(default=True)
    workflow_state = StateField(related_name="social_posts")
    like_count = models.PositiveIntegerField(default=0)
    comment_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "social_feed_post"
        ordering = ["-created_at"]
        verbose_name = "Social Post"
        verbose_name_plural = "Social Posts"

    def __str__(self):
        return self.title


class SocialPostLike(BaseModel):
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="likes",
    )

    class Meta:
        db_table = "social_feed_like"
        verbose_name = "Like"
        verbose_name_plural = "Likes"
        constraints = [
            models.UniqueConstraint(
                fields=["post", "created_by"],
                name="unique_post_like_per_user",
            ),
        ]

    def __str__(self):
        return f"{self.created_by} likes {self.post.title}"


class SocialPostComment(BaseModel):
    post = models.ForeignKey(
        SocialPost,
        on_delete=models.CASCADE,
        related_name="comments",
    )
    content = models.TextField()

    class Meta:
        db_table = "social_feed_comment"
        ordering = ["created_at"]
        verbose_name = "Comment"
        verbose_name_plural = "Comments"

    def __str__(self):
        return f"Comment by {self.created_by} on {self.post.title}"
