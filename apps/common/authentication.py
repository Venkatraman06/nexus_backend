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

        try:
            kc = _keycloak_openid()
            token_info = None
            try:
                token_info = kc.userinfo(access_token)
            except Exception:
                token_info = kc.introspect(access_token)
                if not token_info.get("active"):
                    import jwt
                    token_info = jwt.decode(access_token, options={"verify_signature": False})

            user_id = token_info.get("sub")
            if not user_id:
                raise AuthenticationFailed("Token missing subject claim")

            user_info = token_info
            username = user_info.get("preferred_username") or token_info.get("preferred_username")

            from apps.accounts.models import Employee
            from apps.accounts.services import KeycloakSyncService
            from django.utils import timezone

            user = Employee.objects.filter(keycloak_id=user_id).first()
            if user is None and username:
                user = Employee.objects.filter(username=username).first()
                if user and not user.keycloak_id:
                    user.keycloak_id = user_id
                    user.last_login = timezone.now()
                    user.save(update_fields=["keycloak_id", "last_login"])
            if user is None:
                try:
                    user = KeycloakSyncService().sync_one(user_id)
                except Exception as exc:
                    logger.error("Failed to sync employee %s from Keycloak: %s", user_id, exc)
                    raise AuthenticationFailed("Employee not found and sync failed.")

            # Resolve and attach Keycloak permissions (cached in Redis)
            from packages.keycloak.permissions import PermissionResolver
            realm_perms = PermissionResolver().resolve_permissions(user_id)

            # Also extract client roles from the token directly
            import base64, json as _json
            try:
                payload_part = access_token.split(".")[1]
                padding = 4 - len(payload_part) % 4
                if padding != 4:
                    payload_part += "=" * padding
                token_payload = _json.loads(base64.b64decode(payload_part))
                client_roles = (
                    token_payload
                    .get("resource_access", {})
                    .get(settings.KEYCLOAK_CLIENT_ID, {})
                    .get("roles", [])
                )
            except Exception as exc:
                logger.warning("Could not decode client roles from token: %s", exc)
                client_roles = []

            # Merge realm + client roles (deduped, existing behavior preserved)
            perms = set(realm_perms + client_roles)
            
            # Map legacy follow-up permissions to new independent meeting permissions
            if "pmt.crm.followup.view" in perms:
                perms.add("pmt.crm.meeting.view")
            if "pmt.crm.followup.create" in perms:
                perms.add("pmt.crm.meeting.create")
            if "pmt.crm.followup.update" in perms:
                perms.add("pmt.crm.meeting.update")
            if "pmt.crm.followup.delete" in perms:
                perms.add("pmt.crm.meeting.delete")
            if "pmt.crm.followup.transition" in perms:
                perms.add("pmt.crm.meeting.transition")
            if "pmt.crm.followup.view_all" in perms:
                perms.add("pmt.crm.meeting.view_all")
            
            request.user_permissions = list(perms)
            request.keycloak_user_id = user_id

            return user, None

        except AuthenticationFailed:
            raise
        except Exception as exc:
            logger.error("Keycloak token validation failed: %s", exc)
            raise AuthenticationFailed(f"Token validation failed: {exc}")
