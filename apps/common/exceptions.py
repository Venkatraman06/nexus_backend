import logging

from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import (
    AuthenticationFailed,
    NotAuthenticated,
    PermissionDenied,
    ValidationError,
)
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    response = exception_handler(exc, context)

    if response is not None:
        if isinstance(exc, (AuthenticationFailed, NotAuthenticated)):
            response.data = {
                "status": "error",
                "code": response.status_code,
                "message": "Authentication failed",
                "errors": response.data,
            }
        elif isinstance(exc, PermissionDenied):
            response.data = {
                "status": "error",
                "code": response.status_code,
                "message": "Permission denied",
                "errors": response.data,
            }
        elif isinstance(exc, ValidationError):
            response.data = {
                "status": "error",
                "code": response.status_code,
                "message": "Validation failed",
                "errors": response.data,
            }
        else:
            response.data = {
                "status": "error",
                "code": response.status_code,
                "message": str(exc),
                "errors": response.data,
            }
        return response

    logger.exception("Unhandled exception: %s", exc)
    return Response(
        {
            "status": "error",
            "code": status.HTTP_500_INTERNAL_SERVER_ERROR,
            "message": "Internal server error",
            "errors": str(exc),
        },
        status=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )
