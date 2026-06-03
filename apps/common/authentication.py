import logging

from django.conf import settings
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed

logger = logging.getLogger(__name__)


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

            user_id = token_info.get("sub")
            if not user_id:
                raise AuthenticationFailed("Token missing subject claim")

            user_info = kc.userinfo(access_token)
            username = user_info.get("preferred_username") or token_info.get("preferred_username")

            from apps.accounts.models import Employee
            user = Employee.objects.filter(keycloak_id=user_id).first()
            if user is None and username:
                user = Employee.objects.filter(username=username).first()
            if user is None:
                raise AuthenticationFailed("Employee not found. Run sync_employees first.")

            # Resolve and attach Keycloak permissions (cached in Redis)
            from packages.keycloak.permissions import PermissionResolver
            request.user_permissions = PermissionResolver().resolve_permissions(user_id)
            request.keycloak_user_id = user_id

            return user, None

        except AuthenticationFailed:
            raise
        except Exception as exc:
            logger.error("Keycloak token validation failed: %s", exc)
            raise AuthenticationFailed(f"Token validation failed: {exc}")
