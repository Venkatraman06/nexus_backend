"""
Auth API — all Keycloak-backed endpoints:
  POST /auth/token/          — login with username + password
  POST /auth/token/refresh/  — exchange refresh token
  POST /auth/logout/         — invalidate refresh token
  POST /auth/forgot-password/ — trigger Keycloak password-reset email
"""
import logging

from django.conf import settings
from drf_spectacular.utils import extend_schema, OpenApiResponse
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)


def _kc_openid():
    from keycloak import KeycloakOpenID
    return KeycloakOpenID(
        server_url=settings.KEYCLOAK_SERVER_URL,
        realm_name=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
    )


def _kc_admin():
    from keycloak import KeycloakAdmin
    return KeycloakAdmin(
        server_url=settings.KEYCLOAK_SERVER_URL,
        realm_name=settings.KEYCLOAK_REALM,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
        verify=True,
    )


def _fetch_employee(kc, access_token):
    """Introspect token and look up the matching Employee record."""
    from apps.accounts.models import Employee
    try:
        token_info = kc.introspect(access_token)
        user_id = token_info.get("sub")
        if not user_id:
            return None, None
        emp = Employee.objects.filter(keycloak_id=user_id).first()
        if emp:
            return emp, user_id
        preferred = token_info.get("preferred_username")
        emp = Employee.objects.filter(username=preferred).first() if preferred else None
        return emp, user_id
    except Exception:
        return None, None


# ──────────────────────────────────────────────────────────
# POST /auth/token/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Login with username and password",
    request={"application/json": {
        "type": "object",
        "properties": {
            "username": {"type": "string", "example": "john.doe"},
            "password": {"type": "string", "example": "secret"},
        },
        "required": ["username", "password"],
    }},
    responses={
        200: OpenApiResponse(description="Access token + refresh token + user info"),
        401: OpenApiResponse(description="Invalid credentials"),
        503: OpenApiResponse(description="Keycloak unavailable"),
    },
)
class TokenView(APIView):
    """Obtain access + refresh tokens using Keycloak username / password."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        username = (request.data.get("username") or "").strip()
        password = (request.data.get("password") or "").strip()
        if not username or not password:
            return Response(
                {"error": "username and password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            kc = _kc_openid()
            token_data = kc.token(username, password)
        except Exception as exc:
            err = str(exc).lower()
            if "401" in err or "invalid_grant" in err or "unauthorized" in err:
                return Response(
                    {"error": "Invalid username or password"},
                    status=status.HTTP_401_UNAUTHORIZED,
                )
            logger.error("Keycloak token error: %s", exc)
            return Response(
                {"error": "Authentication service unavailable"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        access_token = token_data.get("access_token")
        emp, _ = _fetch_employee(kc, access_token)

        user_data = None
        if emp:
            from django.utils import timezone
            previous_login = emp.last_login
            emp.last_login = timezone.now()
            emp.save(update_fields=["last_login"])

            user_data = {
                "id":           str(emp.id),
                "username":     emp.username,
                "full_name":    emp.full_name,
                "email":        emp.email,
                "is_pmo":       emp.is_pmo,
                "is_manager":   emp.is_manager,
                "is_staff":     emp.is_staff,
                "last_login":   previous_login.isoformat() if previous_login else None,
            }

        return Response({
            "access_token":  access_token,
            "refresh_token": token_data.get("refresh_token"),
            "token_type":    "bearer",
            "expires_in":    token_data.get("expires_in"),
            "user":          user_data,
        })


# ──────────────────────────────────────────────────────────
# POST /auth/token/refresh/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Refresh an access token",
    request={"application/json": {
        "type": "object",
        "properties": {"refresh_token": {"type": "string"}},
        "required": ["refresh_token"],
    }},
    responses={
        200: OpenApiResponse(description="New access + refresh tokens"),
        401: OpenApiResponse(description="Invalid or expired refresh token"),
    },
)
class TokenRefreshView(APIView):
    """Exchange a refresh token for a new access token."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        refresh_token = (request.data.get("refresh_token") or "").strip()
        if not refresh_token:
            return Response(
                {"error": "refresh_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            kc = _kc_openid()
            token_data = kc.refresh_token(refresh_token)
        except Exception as exc:
            logger.error("Token refresh failed: %s", exc)
            return Response(
                {"error": "Invalid or expired refresh token"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        return Response({
            "access_token":  token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "token_type":    "bearer",
            "expires_in":    token_data.get("expires_in"),
        })


# ──────────────────────────────────────────────────────────
# POST /auth/logout/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Logout — invalidate refresh token",
    request={"application/json": {
        "type": "object",
        "properties": {"refresh_token": {"type": "string"}},
        "required": ["refresh_token"],
    }},
    responses={
        200: OpenApiResponse(description="Logged out"),
        400: OpenApiResponse(description="refresh_token missing"),
    },
)
class LogoutView(APIView):
    """Invalidate the user's Keycloak session (requires Bearer token)."""

    def post(self, request):
        refresh_token = (request.data.get("refresh_token") or "").strip()
        if not refresh_token:
            return Response(
                {"error": "refresh_token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Invalidate Redis permission cache for this user
        keycloak_user_id = getattr(request, "keycloak_user_id", None)
        if keycloak_user_id:
            from packages.keycloak.permissions import invalidate_permissions_cache
            invalidate_permissions_cache(keycloak_user_id)

        try:
            kc = _kc_openid()
            kc.logout(refresh_token)
        except Exception as exc:
            logger.warning("Keycloak logout error (non-fatal): %s", exc)

        return Response({"message": "Logged out successfully."})


# ──────────────────────────────────────────────────────────
# POST /auth/forgot-password/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Trigger password reset email via Keycloak",
    request={"application/json": {
        "type": "object",
        "properties": {"email": {"type": "string", "format": "email"}},
        "required": ["email"],
    }},
    responses={
        200: OpenApiResponse(description="Reset email sent (if account exists)"),
        400: OpenApiResponse(description="email field missing"),
    },
)
class ForgotPasswordView(APIView):
    """Send Keycloak 'UPDATE_PASSWORD' action email to the user."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        email = (request.data.get("email") or "").strip().lower()
        if not email:
            return Response(
                {"error": "email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Always respond 200 to avoid user enumeration
        try:
            from apps.accounts.models import Employee
            emp = Employee.objects.filter(email=email).first()
            if emp and emp.keycloak_id:
                admin = _kc_admin()
                admin.send_update_account(emp.keycloak_id, ["UPDATE_PASSWORD"])
        except Exception as exc:
            logger.error("Forgot-password error: %s", exc)

        return Response({
            "message": "If an account with that email exists, a password reset link has been sent."
        })
