"""
Future real-time delivery via WebSocket.

When enabled, the notification engine will broadcast to connected clients
after creating in-app records. Hook point: NotificationEngine.process().
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def broadcast_notification(recipient_id: str, notification_data: dict) -> None:
    """
    Push a notification to the recipient's WebSocket channel.
    Implement with Django Channels / Redis pub-sub when ready.
    """
    logger.debug("WebSocket broadcast stub for %s: %s", recipient_id, notification_data.get("title"))
