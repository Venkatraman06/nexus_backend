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

        token_data = None
        user_id = None
        emp = None

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
            from apps.accounts.local_auth import authenticate_local_employee, generate_local_jwt
            local_emp, local_err = authenticate_local_employee(username, password)
            if local_emp:
                emp = local_emp
                token_data = generate_local_jwt(emp)
            else:
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

        if not emp:
            try:
                token_info = kc.introspect(access_token)
                user_id = token_info.get("sub")
            except Exception:
                pass

        from apps.accounts.models import Employee
        from django.utils import timezone

        if user_id and not emp:
            emp = Employee.objects.filter(keycloak_id=user_id).first()
            if emp is None:
                emp = Employee.objects.filter(username=username).first() or Employee.objects.filter(email=username).first()
                if emp and not emp.keycloak_id:
                    emp.keycloak_id = user_id

        if emp:
            emp.last_login = timezone.now()
            emp.save(update_fields=["last_login", "keycloak_id"] if emp.keycloak_id else ["last_login"])
            user_data = {
                "id": str(emp.id),
                "username": emp.username,
                "full_name": emp.full_name,
                "email": emp.email,
                "is_pmo": emp.is_pmo,
                "is_manager": emp.is_manager,
                "is_staff": emp.is_staff,
            }
        else:
            user_data = None

        return Response({
            "access_token": access_token,
            "refresh_token": token_data.get("refresh_token"),
            "expires_in": token_data.get("expires_in"),
            "user": user_data,
        })
