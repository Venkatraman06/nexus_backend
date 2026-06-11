from django.utils import timezone
from rest_framework import status
from rest_framework.response import Response


def success_response(data=None, message="Operation successful", status_code=status.HTTP_200_OK):
    return Response({
        "status": "success",
        "code": status_code,
        "message": message,
        "data": data,
        "timestamp": timezone.now().isoformat(),
    }, status=status_code)


def error_response(message="Operation failed", errors=None, status_code=status.HTTP_400_BAD_REQUEST):
    return Response({
        "status": "error",
        "code": status_code,
        "message": message,
        "errors": errors,
        "timestamp": timezone.now().isoformat(),
    }, status=status_code)


class CommonResponseMixin:
    def finalize_response(self, request, response, *args, **kwargs):
        if hasattr(response, "data") and isinstance(response.data, dict):
            if "status" not in response.data:
                if response.status_code >= 400:
                    response.data = {
                        "status": "error",
                        "code": response.status_code,
                        "message": response.data.get("detail", "Error occurred"),
                        "errors": response.data,
                        "timestamp": timezone.now().isoformat(),
                    }
                else:
                    msg = response.data.pop("message", "Operation successful")
                    response.data = {
                        "status": "success",
                        "code": response.status_code,
                        "message": msg,
                        "data": response.data,
                        "timestamp": timezone.now().isoformat(),
                    }
        return super().finalize_response(request, response, *args, **kwargs)
