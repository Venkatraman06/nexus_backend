"""
Broadcast helper shared by both mutation paths (REST views/serializers and
the WebSocket consumer) so a message created/edited/deleted via REST reaches
already-connected WebSocket clients too — not just requests that originated
on the socket itself.
"""
import json
import logging

from rest_framework.utils.encoders import JSONEncoder

logger = logging.getLogger(__name__)


class RequestContext:
    """Stand-in for DRF's serializer context requirement of `request.user`,
    for broadcasts triggered outside an actual request (WS consumer events,
    Celery tasks like the ClamAV scan result)."""

    def __init__(self, user):
        self.user = user


def to_json_safe(data):
    """
    Round-trip through DRF's JSON encoder so UUID/datetime/Decimal values
    become plain str/JSON types. Needed because DRF's PrimaryKeyRelatedField
    (used for FK fields like `conversation`/`reply_to`) returns the raw
    `.pk` value — a real uuid.UUID instance, not a string — in
    `serializer.data`. That's fine for DRF's HTTP renderer (which knows how
    to encode UUID), but channels_redis' msgpack serializer for group_send
    payloads does not, and raises TypeError at broadcast time.
    """
    return json.loads(json.dumps(data, cls=JSONEncoder))


def broadcast_to_conversation(conversation_id, event_type, message_data) -> None:
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        return
    try:
        async_to_sync(channel_layer.group_send)(
            f"conversation_{conversation_id}",
            {"type": event_type, "message": to_json_safe(message_data)},
        )
    except Exception:
        logger.exception("Failed to broadcast %s to conversation %s", event_type, conversation_id)
