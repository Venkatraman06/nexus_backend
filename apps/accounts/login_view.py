"""POST /api/v1/auth/login/ — username + password → Keycloak token + user info"""
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from django.conf import settings


@extend_schema(
    tags=["auth"],
    request={"application/json": {"type": "object", "properties": {
        "username": {"type": "string"},
        "password": {"type": "string"},
    }, "required": ["username", "password"]}},
    responses={200: OpenApiResponse(description="Token + user info")},
)
class LoginView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = request.data.get("username", "").strip()
        password = request.data.get("password", "").strip()

        if not username or not password:
            return Response(
                {"error": "username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            from keycloak import KeycloakOpenID
            kc = KeycloakOpenID(
                server_url=settings.KEYCLOAK_SERVER_URL,
                realm_name=settings.KEYCLOAK_REALM,
                client_id=settings.KEYCLOAK_CLIENT_ID,
                client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
            )
            token_data = kc.token(username, password)
        except Exception as exc:
            err = str(exc)
            if "401" in err or "invalid_grant" in err.lower() or "Unauthorized" in err:
                return Response(
                    {"error": "Invalid username or password"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            return Response(
                {"error": "Authentication service unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        access_token = token_data.get("access_token")
        user_id = None

        try:
            token_info = kc.introspect(access_token)
            user_id = token_info.get("sub")
        except Exception:
            pass

        user_data = None
        if user_id:
            from apps.accounts.models import Employee
            emp = Employee.objects.filter(keycloak_id=user_id).first()
            if emp is None:
                emp = Employee.objects.filter(username=username).first()
            if emp:
                user_data = {
                    "id": str(emp.id),
                    "username": emp.username,
                    "full_name": emp.full_name,
                    "email": emp.email,
                    "is_pmo": emp.is_pmo,
                    "is_manager": emp.is_manager,
                    "is_staff": emp.is_staff,
                }

        return Response({
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "user": user_data,
        })
