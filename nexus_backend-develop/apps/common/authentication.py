import logging
# from packages.keycloak.permissions import PermissionResolver
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

        # 1. Try to decode as a local HS256 JWT using our SECRET_KEY
        try:
            import jwt
            token_info = jwt.decode(access_token, settings.SECRET_KEY, algorithms=["HS256"])
            # If successfully decoded, this is a local fallback session.
            username = token_info.get("preferred_username")
            user_id = token_info.get("sub")

            from apps.accounts.models import Employee
            user = Employee.objects.filter(username=username).first()
            if not user:
                raise AuthenticationFailed("Employee not found.")

            # Populate fallback permissions from role_permissions.json or settings
            user_permissions = []
            group_name = user.keycloak_group
            if group_name:
                import json
                import os
                role_path = os.path.join(settings.BASE_DIR, "role_permissions.json")
                if os.path.exists(role_path):
                    try:
                        with open(role_path, "r", encoding="utf-8") as rf:
                            role_perms_map = json.load(rf)
                            user_permissions = role_perms_map.get(group_name, [])
                    except Exception as e:
                        logger.error("Failed to load local role permissions: %s", e)

            request.user_permissions = user_permissions
            request.keycloak_user_id = user_id or str(user.id)
            return user, None

        except jwt.PyJWTError:
            # If not a local JWT or signature validation fails, fall through to Keycloak
            pass

        # 2. Standard Keycloak Introspection
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

    # def authenticate(self, request):
    #     auth_header = request.headers.get("Authorization", "")
    #     if not auth_header.startswith("Bearer "):
    #         return None

    #     access_token = auth_header.split(" ", 1)[1]

    #     try:
    #         import base64, json
    #         parts = access_token.split('.')
    #         payload = parts[1] + '=' * (4 - len(parts[1]) % 4)
    #         token_info = json.loads(base64.b64decode(payload))

    #         user_id = token_info.get("sub")
    #         if not user_id:
    #             raise AuthenticationFailed("Token missing subject claim")

    #         username = token_info.get("preferred_username")

    #         from apps.accounts.models import Employee
    #         user = Employee.objects.filter(keycloak_id=user_id).first()
    #         if user is None and username:
    #             user = Employee.objects.filter(username=username).first()
    #         if user is None:
    #             raise AuthenticationFailed("Employee not found. Run sync_employees first.")

           
    #         request.user_permissions = PermissionResolver().resolve_permissions(user_id)
    #         request.keycloak_user_id = user_id

    #         return user, None

    #     except AuthenticationFailed:
    #         raise
    #     except Exception as exc:
    #         logger.error("Keycloak token validation failed: %s", exc)
    #         raise AuthenticationFailed(f"Token validation failed: {exc}")
