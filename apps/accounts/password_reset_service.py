import logging
import random
import secrets
import string
from dataclasses import dataclass

from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

OTP_CACHE_PREFIX = "pwd_reset_otp:"
RESET_TOKEN_PREFIX = "pwd_reset_token:"
ONBOARD_TOKEN_PREFIX = "onboard_token:"
RATE_LIMIT_PREFIX = "pwd_reset_rate:"


@dataclass
class ResetContext:
    employee_id: str
    keycloak_id: str
    email: str
    username: str
    full_name: str


def _otp_ttl() -> int:
    return settings.OTP_EXPIRY_MINUTES * 60


def _reset_token_ttl() -> int:
    return settings.RESET_TOKEN_EXPIRY_MINUTES * 60


def _onboard_token_ttl() -> int:
    return settings.ONBOARD_TOKEN_EXPIRY_HOURS * 3600


def _generate_otp() -> str:
    return "".join(random.SystemRandom().choice(string.digits) for _ in range(6))


def _lookup_employee(identifier: str):
    from apps.accounts.models import Employee

    identifier = identifier.strip()
    if not identifier:
        return None

    emp = Employee.objects.filter(email__iexact=identifier).first()
    if emp:
        return emp

    return Employee.objects.filter(username__iexact=identifier).first()


def _to_context(emp) -> ResetContext:
    return ResetContext(
        employee_id=str(emp.id),
        keycloak_id=emp.keycloak_id or "",
        email=emp.email,
        username=emp.username,
        full_name=emp.full_name or emp.username,
    )


def _rate_limit_key(identifier: str) -> str:
    return f"{RATE_LIMIT_PREFIX}{identifier.lower()}"


def is_rate_limited(identifier: str, max_requests: int = 3, window_seconds: int = 900) -> bool:
    key = _rate_limit_key(identifier)
    count = cache.get(key, 0)
    return count >= max_requests


def increment_rate_limit(identifier: str, window_seconds: int = 900) -> None:
    key = _rate_limit_key(identifier)
    count = cache.get(key, 0)
    cache.set(key, count + 1, window_seconds)


def request_password_reset_otp(identifier: str) -> tuple[bool, str | None, ResetContext | None]:
    """
    Generate and store OTP for the given username/email.
    Returns (sent, otp_code, context). otp_code is only for logging in dev;
    production callers should email it and discard.
    """
    if is_rate_limited(identifier):
        return False, None, None

    emp = _lookup_employee(identifier)
    if not emp or not emp.keycloak_id:
        increment_rate_limit(identifier)
        return False, None, None

    otp = _generate_otp()
    ctx = _to_context(emp)
    cache_key = f"{OTP_CACHE_PREFIX}{ctx.employee_id}"
    cache.set(
        cache_key,
        {
            "otp": otp,
            "attempts": 0,
            "keycloak_id": ctx.keycloak_id,
            "email": ctx.email,
            "username": ctx.username,
            "full_name": ctx.full_name,
        },
        _otp_ttl(),
    )
    increment_rate_limit(identifier)
    return True, otp, ctx


def verify_password_reset_otp(identifier: str, otp: str) -> tuple[bool, str | None, str | None]:
    """
    Verify OTP. Returns (success, reset_token, error_message).
    """
    emp = _lookup_employee(identifier)
    if not emp:
        return False, None, "Invalid verification code."

    cache_key = f"{OTP_CACHE_PREFIX}{emp.id}"
    stored = cache.get(cache_key)
    if not stored:
        return False, None, "Verification code has expired. Please request a new one."

    attempts = stored.get("attempts", 0) + 1
    if attempts > settings.OTP_MAX_ATTEMPTS:
        cache.delete(cache_key)
        return False, None, "Too many failed attempts. Please request a new code."

    stored["attempts"] = attempts
    cache.set(cache_key, stored, _otp_ttl())

    if stored.get("otp") != otp.strip():
        return False, None, "Invalid verification code."

    cache.delete(cache_key)

    reset_token = secrets.token_urlsafe(32)
    cache.set(
        f"{RESET_TOKEN_PREFIX}{reset_token}",
        {
            "keycloak_id": stored["keycloak_id"],
            "employee_id": str(emp.id),
        },
        _reset_token_ttl(),
    )
    return True, reset_token, None


def create_onboard_token(employee_id: str, keycloak_id: str) -> str:
    token = secrets.token_urlsafe(32)
    cache.set(
        f"{ONBOARD_TOKEN_PREFIX}{token}",
        {"keycloak_id": keycloak_id, "employee_id": employee_id},
        _onboard_token_ttl(),
    )
    return token


def validate_reset_token(token: str) -> dict | None:
    return cache.get(f"{RESET_TOKEN_PREFIX}{token}")


def validate_onboard_token(token: str) -> dict | None:
    return cache.get(f"{ONBOARD_TOKEN_PREFIX}{token}")


def set_keycloak_password(keycloak_id: str, password: str, temporary: bool = False) -> None:
    from apps.accounts.auth_views import _kc_admin

    admin = _kc_admin()
    admin.set_user_password(keycloak_id, password, temporary=temporary)


def reset_password_with_token(token: str, password: str, *, onboard: bool = False) -> tuple[bool, str | None]:
    prefix = ONBOARD_TOKEN_PREFIX if onboard else RESET_TOKEN_PREFIX
    cache_key = f"{prefix}{token}"
    data = cache.get(cache_key)
    if not data or not data.get("keycloak_id"):
        return False, "Invalid or expired reset link. Please request a new one."

    try:
        set_keycloak_password(data["keycloak_id"], password, temporary=False)
    except Exception as exc:
        logger.error("Keycloak password reset failed: %s", exc)
        return False, "Unable to update password. Please try again later."

    cache.delete(cache_key)
    return True, None
