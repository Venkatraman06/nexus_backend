"""
Auth API — all Keycloak-backed endpoints:
  POST /auth/token/                    — login with username + password
  POST /auth/token/refresh/              — exchange refresh token
  POST /auth/logout/                   — invalidate refresh token
  POST /auth/forgot-password/          — request 6-digit OTP (username or email)
  POST /auth/forgot-password/verify/   — verify OTP, get reset token
  POST /auth/reset-password/           — set new password with reset token
  GET  /auth/reset-password/validate/  — validate reset/onboard token
  POST /auth/onboard/set-password/     — set password from onboarding link
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
    summary="Request password reset OTP (username or email)",
    request={"application/json": {
        "type": "object",
        "properties": {
            "identifier": {"type": "string", "example": "john.doe"},
        },
        "required": ["identifier"],
    }},
    responses={
        200: OpenApiResponse(description="OTP sent if account exists"),
        400: OpenApiResponse(description="identifier missing"),
        429: OpenApiResponse(description="Too many requests"),
    },
)
class ForgotPasswordView(APIView):
    """Step 1: send a 6-digit verification code to the user's email."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identifier = (request.data.get("identifier") or request.data.get("email") or "").strip()
        if not identifier:
            return Response(
                {"error": "username or email is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.accounts.password_reset_service import (
            is_rate_limited,
            request_password_reset_otp,
        )
        from apps.accounts.email_service import send_password_reset_otp_email

        if is_rate_limited(identifier):
            return Response(
                {"error": "Too many reset attempts. Please try again later."},
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        sent, otp, ctx = request_password_reset_otp(identifier)
        if sent and otp and ctx:
            send_password_reset_otp_email(
                to=ctx.email,
                full_name=ctx.full_name,
                otp=otp,
            )

        return Response({
            "message": "If an account with that username or email exists, a verification code has been sent.",
        })


# ──────────────────────────────────────────────────────────
# POST /auth/forgot-password/verify/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Verify password reset OTP",
    request={"application/json": {
        "type": "object",
        "properties": {
            "identifier": {"type": "string"},
            "otp": {"type": "string", "example": "123456"},
        },
        "required": ["identifier", "otp"],
    }},
    responses={
        200: OpenApiResponse(description="OTP verified — reset_token returned"),
        400: OpenApiResponse(description="Invalid or expired OTP"),
    },
)
class VerifyResetOtpView(APIView):
    """Step 2: verify the 6-digit code and receive a short-lived reset token."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        identifier = (request.data.get("identifier") or "").strip()
        otp = (request.data.get("otp") or "").strip()

        if not identifier or not otp:
            return Response(
                {"error": "identifier and otp are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        from apps.accounts.password_reset_service import verify_password_reset_otp

        ok, reset_token, err = verify_password_reset_otp(identifier, otp)
        if not ok:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"reset_token": reset_token})


# ──────────────────────────────────────────────────────────
# GET /auth/reset-password/validate/
# POST /auth/reset-password/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Validate a reset or onboard token",
    parameters=[{"name": "token", "in": "query", "required": True, "schema": {"type": "string"}}],
    responses={
        200: OpenApiResponse(description="Token is valid"),
        400: OpenApiResponse(description="Token invalid or expired"),
    },
)
class ValidateResetTokenView(APIView):
    """Check whether a reset/onboard token is still valid before showing the form."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def get(self, request):
        token = (request.query_params.get("token") or "").strip()
        onboard = request.query_params.get("onboard", "").lower() in ("1", "true", "yes")

        if not token:
            return Response({"error": "token is required"}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.password_reset_service import validate_onboard_token, validate_reset_token

        data = validate_onboard_token(token) if onboard else validate_reset_token(token)
        if not data:
            return Response({"error": "Invalid or expired link."}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"valid": True})


@extend_schema(
    tags=["Authentication"],
    summary="Set a new password using reset token",
    request={"application/json": {
        "type": "object",
        "properties": {
            "reset_token": {"type": "string"},
            "password": {"type": "string"},
            "confirm_password": {"type": "string"},
        },
        "required": ["reset_token", "password", "confirm_password"],
    }},
    responses={
        200: OpenApiResponse(description="Password updated"),
        400: OpenApiResponse(description="Validation error"),
    },
)
class ResetPasswordView(APIView):
    """Step 3: set new password after OTP verification."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        reset_token = (request.data.get("reset_token") or "").strip()
        password = request.data.get("password") or ""
        confirm = request.data.get("confirm_password") or ""

        if not reset_token:
            return Response({"error": "reset_token is required"}, status=status.HTTP_400_BAD_REQUEST)

        if password != confirm:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.password_validators import validate_password_strength
        from apps.accounts.password_reset_service import reset_password_with_token

        errors = validate_password_strength(password)
        if errors:
            return Response({"error": errors[0], "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        ok, err = reset_password_with_token(reset_token, password, onboard=False)
        if not ok:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Password updated successfully. You can now sign in."})


# ──────────────────────────────────────────────────────────
# POST /auth/onboard/set-password/
# ──────────────────────────────────────────────────────────

@extend_schema(
    tags=["Authentication"],
    summary="Set password from employee onboarding link",
    request={"application/json": {
        "type": "object",
        "properties": {
            "token": {"type": "string"},
            "password": {"type": "string"},
            "confirm_password": {"type": "string"},
        },
        "required": ["token", "password", "confirm_password"],
    }},
    responses={
        200: OpenApiResponse(description="Password set"),
        400: OpenApiResponse(description="Validation error"),
    },
)
class OnboardSetPasswordView(APIView):
    """Set password from the welcome email link (no OTP required)."""
    permission_classes = [AllowAny]
    authentication_classes = []

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        password = request.data.get("password") or ""
        confirm = request.data.get("confirm_password") or ""

        if not token:
            return Response({"error": "token is required"}, status=status.HTTP_400_BAD_REQUEST)

        if password != confirm:
            return Response({"error": "Passwords do not match."}, status=status.HTTP_400_BAD_REQUEST)

        from apps.accounts.password_validators import validate_password_strength
        from apps.accounts.password_reset_service import reset_password_with_token

        errors = validate_password_strength(password)
        if errors:
            return Response({"error": errors[0], "errors": errors}, status=status.HTTP_400_BAD_REQUEST)

        ok, err = reset_password_with_token(token, password, onboard=True)
        if not ok:
            return Response({"error": err}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"message": "Password set successfully. You can now sign in."})
