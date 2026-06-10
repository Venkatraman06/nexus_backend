import logging
# from packages.keycloak.permissions import PermissionResolver
from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


def _extract_jwt_sub(access_token: str) -> str | None:
    """Decode JWT locally and extract the `sub` claim.

    Keycloak 26 sometimes omits `sub` from the introspection endpoint
    response.  This helper reads it straight from the JWT payload.
    """
    import base64, json
    try:
        parts = access_token.split(".")
        if len(parts) < 2:
            return None
        payload_b64 = parts[1]
        padding = 4 - len(payload_b64) % 4
        if padding != 4:
            payload_b64 += "=" * padding
        decoded = base64.b64decode(payload_b64)
        payload = json.loads(decoded)
        return payload.get("sub")
    except Exception:
        return None


def _keycloak_openid():
    from keycloak import KeycloakOpenID
    return KeycloakOpenID(
        server_url=settings.KEYCLOAK_SERVER_URL,
        client_id=settings.KEYCLOAK_CLIENT_ID,
        realm_name=settings.KEYCLOAK_REALM,
        client_secret_key=settings.KEYCLOAK_CLIENT_SECRET_KEY,
    )


class KeycloakAuthentication(BaseAuthentication):
    def authenticate_header(self, request):
        # Returning a non-empty string keeps DRF's status code as 401
        # (without this DRF downgrades AuthenticationFailed to 403)
        return 'Bearer realm="api"'

    def authenticate(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return None

        access_token = auth_header.split(" ", 1)[1]

        try:
            kc = _keycloak_openid()
            token_info = kc.introspect(access_token)

            if not token_info.get("active"):
                raise AuthenticationFailed("Invalid or expired token")

            # Keycloak 26 sometimes omits the "sub" claim from introspection.
            # Fall back to decoding the JWT locally, then to preferred_username.
            user_id = token_info.get("sub")
            if not user_id:
                user_id = _extract_jwt_sub(access_token)

            # Keycloak lowercases usernames — will do case-insensitive lookup below
            username = token_info.get("preferred_username")
            if not user_id and not username:
                raise AuthenticationFailed("Token missing subject claim")

            from apps.accounts.models import Employee
            user = None
            if user_id:
                user = Employee.objects.filter(keycloak_id=user_id).first()
            if user is None and username:
                user = Employee.objects.filter(username__iexact=username).first()
            if user is None:
                raise AuthenticationFailed("Employee not found. Run sync_employees first.")

            # Resolve and attach Keycloak permissions (cached in Redis)
            from packages.keycloak.permissions import PermissionResolver
            kc_user_id = user_id or user.keycloak_id or ""
            request.user_permissions = PermissionResolver().resolve_permissions(kc_user_id)
            request.keycloak_user_id = kc_user_id

            return user, None

        except AuthenticationFailed:
            raise
        except Exception as exc:
            logger.error("Keycloak token validation failed: %s", exc)
            raise AuthenticationFailed(f"Token validation failed: {exc}")
