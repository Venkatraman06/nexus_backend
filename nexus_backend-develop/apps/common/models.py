import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class BaseModel(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    is_active = models.BooleanField(default=True)
    is_deleted = models.BooleanField(default=False)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="%(app_label)s_%(class)s_updated",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True

    def soft_delete(self, user=None):
        self.is_deleted = True
        self.is_active = False
        if user:
            self.updated_by = user
        self.updated_at = timezone.now()
        self.save(update_fields=["is_deleted", "is_active", "updated_by", "updated_at"])

    def restore(self, user=None):
        self.is_deleted = False
        self.is_active = True
        if user:
            self.updated_by = user
        self.updated_at = timezone.now()
        self.save(update_fields=["is_deleted", "is_active", "updated_by", "updated_at"])


class ActiveManager(models.Manager):
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False, is_active=True)
