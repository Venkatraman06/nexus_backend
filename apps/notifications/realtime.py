"""
Real-time delivery via WebSocket, backed by the Channels layer added for
chat (apps/chat/consumers.py::ChatConsumer). Every authenticated WS
connection joins a `user_<employee_id>` group on connect, so any part of
the app — not just chat — can push a live event to a specific user via
that same group. Hook point: NotificationEngine.process().
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def broadcast_notification(recipient_id: str, notification_data: dict) -> None:
    """Push a notification to the recipient's WebSocket connection(s), if any are open."""
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer

    channel_layer = get_channel_layer()
    if channel_layer is None:
        logger.debug("No channel layer configured; skipping WS broadcast for %s", recipient_id)
        return

    try:
        async_to_sync(channel_layer.group_send)(
            f"user_{recipient_id}",
            {"type": "chat.notification.push", "notification": notification_data},
        )
    except Exception:
        logger.exception("WebSocket broadcast failed for %s", recipient_id)
