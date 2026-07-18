"""
Publishes a domain event for new chat messages through the existing
apps.notifications engine — chat does not maintain a separate notification
pipeline. One call gets: an in-app Notification row (shows in the existing
NotificationBell), live delivery via realtime.broadcast_notification
(already Channels-wired from the chat build), and push delivery (the PUSH
channel implemented in apps.notifications.engine._dispatch_external, which
special-cases chat_message events for presence-aware debounced delivery).

Called from both the REST create path (serializers.py) and the WebSocket
path (consumers.py) so neither one skips it.
"""
from .models import ConversationParticipant
from .text import strip_html_preview


def notify_new_message(message: dict, sender) -> None:
    from apps.notifications.constants import EventType, ReferenceType
    from apps.notifications.publisher import publish_event

    recipient_ids = list(
        ConversationParticipant.objects.filter(conversation_id=message["conversation_id"])
        .exclude(employee_id=sender.id)
        .values_list("employee_id", flat=True)
    )
    if not recipient_ids:
        return

    publish_event(
        event_type=EventType.CHAT_MESSAGE_NEW,
        reference_type=ReferenceType.CHAT_MESSAGE,
        reference_id=message["_id"],
        payload={
            "conversation_id": str(message["conversation_id"]),
            "sender_name": sender.full_name,
            "body_preview": strip_html_preview(message.get("body") or ""),
        },
        actor_id=str(sender.id),
        recipient_ids=[str(r) for r in recipient_ids],
        action_url=f"/chat?conversation={message['conversation_id']}",
        async_delivery=True,
    )
