import logging
from datetime import datetime, timedelta
import jwt
from django.conf import settings
from apps.accounts.models import Employee

logger = logging.getLogger(__name__)


def generate_local_jwt(emp: Employee):
    now = datetime.utcnow()
    exp = now + timedelta(days=7)
    keycloak_id = str(emp.keycloak_id or emp.id)

    payload = {
        "sub": keycloak_id,
        "preferred_username": emp.username,
        "email": emp.email,
        "name": emp.full_name,
        "given_name": emp.first_name,
        "family_name": emp.last_name,
        "iat": int(now.timestamp()),
        "exp": int(exp.timestamp()),
        "iss": "local-pmt-backend",
        "resource_access": {
            getattr(settings, "KEYCLOAK_CLIENT_ID", "pmt-app"): {
                "roles": ["*"] if (emp.is_superuser or emp.is_staff) else []
            }
        }
    }
    secret = getattr(settings, "SECRET_KEY", "django-insecure-change-me")
    access_token = jwt.encode(payload, secret, algorithm="HS256")
    refresh_token = jwt.encode({**payload, "token_type": "refresh"}, secret, algorithm="HS256")

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_in": 604800,
    }


def authenticate_local_employee(username, password):
    if not username or not password:
        return None, "username and password are required"

    emp = (
        Employee.objects.filter(username__iexact=username).first()
        or Employee.objects.filter(email__iexact=username).first()
    )
    if emp and emp.check_password(password):
        if not emp.is_active:
            return None, "Account is inactive"
        return emp, None
    return None, "Invalid username or password"
