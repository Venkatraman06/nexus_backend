import logging

from django.db import transaction
from rest_framework import status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from apps.common.response import CommonResponseMixin

logger = logging.getLogger(__name__)


class BaseModelViewSet(CommonResponseMixin, viewsets.ModelViewSet):
    """
    Standard CRUD viewset with soft-delete, audit trail, and common error handling.
    All child viewsets inherit consistent response format.
    """
    http_method_names = ["get", "post", "put", "patch", "delete"]

    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user, updated_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except ValidationError as exc:
            logger.warning("Create validation error: %s", exc.detail)
            raise

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except ValidationError as exc:
            logger.warning("Update validation error: %s", exc.detail)
            raise

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)
