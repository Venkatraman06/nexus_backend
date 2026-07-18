"""
ASGI auth middleware for WebSocket connections (chat).

Resolves `?token=<bearer-token>` on the WS handshake to a Django user by
running it through the same DRF authentication classes configured for the
HTTP API (`REST_FRAMEWORK.DEFAULT_AUTHENTICATION_CLASSES` — KeycloakAuthentication
in production, TestAuthentication under core.settings.test), so WebSocket
auth can never drift from REST auth: there is exactly one place (this
function delegating to the configured classes) that resolves a bearer token
to a user.
"""
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.utils.module_loading import import_string


class _HeaderOnlyRequest:
    """Minimal request shim — DRF auth classes here only read request.headers."""

    def __init__(self, token):
        self.headers = {"Authorization": f"Bearer {token}"} if token else {}


@database_sync_to_async
def resolve_ws_user(token):
    if not token:
        return AnonymousUser()

    for path in settings.REST_FRAMEWORK.get("DEFAULT_AUTHENTICATION_CLASSES", []):
        auth_class = import_string(path)
        try:
            result = auth_class().authenticate(_HeaderOnlyRequest(token))
        except Exception:
            continue
        if result is not None:
            user, _ = result
            return user
    return AnonymousUser()


class TokenAuthMiddleware:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        query_string = scope.get("query_string", b"").decode()
        token = parse_qs(query_string).get("token", [None])[0]
        scope["user"] = await resolve_ws_user(token)
        return await self.inner(scope, receive, send)
