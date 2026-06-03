import uuid

from django.db import models
from django.utils.translation import gettext_lazy as _


class State(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    slug = models.SlugField(max_length=100)
    label = models.CharField(max_length=100, blank=True, default="")
    color_code = models.CharField(max_length=7, blank=True, default="#6366F1")
    content_type = models.ForeignKey(
        "contenttypes.ContentType",
        on_delete=models.CASCADE,
        related_name="workflow_states",
        null=True,
        blank=True,
    )
    order = models.PositiveIntegerField(default=0)
    is_initial = models.BooleanField(default=False)
    is_final = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        from django.utils.text import slugify
        if not self.slug and self.name:
            base = slugify(self.name)
            slug, n = base, 1
            while State.objects.filter(content_type=self.content_type, slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        if not self.label:
            self.label = self.name
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        db_table = "master_workflow_state"
        verbose_name = _("state")
        verbose_name_plural = _("states")
        ordering = ["order"]
        unique_together = ("content_type", "slug")
