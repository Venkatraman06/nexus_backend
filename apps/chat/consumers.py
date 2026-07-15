from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer
from django.utils import timezone

from . import mongo
from .models import ConversationParticipant
from .notify import notify_new_message
from .presence import clear_presence, touch_presence
from .realtime import RequestContext, to_json_safe
from .serializers import MessageSerializer


class ChatConsumer(AsyncJsonWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if not user or not user.is_authenticated:
            await self.close(code=4001)
            return

        self.user = user
        self.user_group = f"user_{user.id}"
        await self.channel_layer.group_add(self.user_group, self.channel_name)

        self.conversation_ids = await self._my_conversation_ids()
        for cid in self.conversation_ids:
            await self.channel_layer.group_add(f"conversation_{cid}", self.channel_name)

        await self.accept()
        await self._touch_presence()
        await self._broadcast_presence("online")

    async def disconnect(self, close_code):
        if not getattr(self, "user", None) or not self.user.is_authenticated:
            return
        await self.channel_layer.group_discard(self.user_group, self.channel_name)
        for cid in self.conversation_ids:
            await self.channel_layer.group_discard(f"conversation_{cid}", self.channel_name)
        await database_sync_to_async(clear_presence)(self.user.id)
        await self._broadcast_presence("offline")

    async def receive_json(self, content, **kwargs):
        handler = {
            "message:send": self._handle_send,
            "message:edit": self._handle_edit,
            "message:delete": self._handle_delete,
            "typing:start": self._handle_typing_start,
            "typing:stop": self._handle_typing_stop,
            "presence:ping": self._handle_presence_ping,
        }.get(content.get("type"))
        if handler:
            await handler(content)

    # -- client-originated events --

    async def _handle_send(self, content):
        conversation_id = content.get("conversation")
        if conversation_id not in {str(c) for c in self.conversation_ids}:
            return
        message = await self._create_message(conversation_id, content)
        if message:
            await self.channel_layer.group_send(
                f"conversation_{conversation_id}",
                {"type": "chat.message.new", "message": message},
            )

    async def _handle_edit(self, content):
        message = await self._edit_message(content.get("message_id"), content.get("body", ""))
        if message:
            await self.channel_layer.group_send(
                f"conversation_{message['conversation']}",
                {"type": "chat.message.updated", "message": message},
            )

    async def _handle_delete(self, content):
        message = await self._delete_message(content.get("message_id"))
        if message:
            await self.channel_layer.group_send(
                f"conversation_{message['conversation']}",
                {"type": "chat.message.deleted", "message": message},
            )

    async def _handle_typing_start(self, content):
        await self._broadcast_typing(content.get("conversation"), True)

    async def _handle_typing_stop(self, content):
        await self._broadcast_typing(content.get("conversation"), False)

    async def _handle_presence_ping(self, content):
        await self._touch_presence()

    async def _broadcast_typing(self, conversation_id, is_typing):
        if not conversation_id or conversation_id not in {str(c) for c in self.conversation_ids}:
            return
        await self.channel_layer.group_send(
            f"conversation_{conversation_id}",
            {
                "type": "chat.typing.update",
                "conversation_id": conversation_id,
                "employee_id": str(self.user.id),
                "is_typing": is_typing,
            },
        )

    # -- group event handlers (dispatched by the channel layer) --

    async def chat_message_new(self, event):
        await self.send_json({"type": "message:new", "message": event["message"]})

    async def chat_message_updated(self, event):
        await self.send_json({"type": "message:updated", "message": event["message"]})

    async def chat_message_deleted(self, event):
        await self.send_json({"type": "message:deleted", "message": event["message"]})

    async def chat_typing_update(self, event):
        if event["employee_id"] == str(self.user.id):
            return
        await self.send_json({
            "type": "typing:update",
            "conversation_id": event["conversation_id"],
            "employee_id": event["employee_id"],
            "is_typing": event["is_typing"],
        })

    async def chat_presence_update(self, event):
        await self.send_json({
            "type": "presence:update",
            "employee_id": event["employee_id"],
            "status": event["status"],
        })

    async def chat_notification_push(self, event):
        await self.send_json({"type": "notification:push", "notification": event["notification"]})

    # -- db helpers --

    @database_sync_to_async
    def _my_conversation_ids(self):
        return [
            str(cid) for cid in ConversationParticipant.objects.filter(
                employee_id=self.user.id,
            ).values_list("conversation_id", flat=True)
        ]

    @database_sync_to_async
    def _create_message(self, conversation_id, content):
        if not ConversationParticipant.objects.filter(
            conversation_id=conversation_id, employee_id=self.user.id,
        ).exists():
            return None

        from .models import Conversation

        message = mongo.create_message(
            conversation_id=conversation_id, sender_id=self.user.id,
            body=content.get("body", ""), reply_to=content.get("reply_to"),
            mentions=content.get("mention_employee_ids") or [],
        )
        Conversation.objects.filter(id=conversation_id).update(last_message_at=timezone.now())
        notify_new_message(message, self.user)
        return to_json_safe(MessageSerializer(message, context={"request": RequestContext(self.user)}).data)

    @database_sync_to_async
    def _edit_message(self, message_id, body):
        message = mongo.get_message(message_id)
        if message is None or message["sender_id"] != str(self.user.id) or message["is_deleted"]:
            return None
        updated = mongo.update_message_body(message_id, body, self.user.id)
        return to_json_safe(MessageSerializer(updated, context={"request": RequestContext(self.user)}).data)

    @database_sync_to_async
    def _delete_message(self, message_id):
        message = mongo.get_message(message_id)
        if message is None or message["sender_id"] != str(self.user.id):
            return None
        updated = mongo.soft_delete_message(message_id, self.user.id)
        return to_json_safe(MessageSerializer(updated, context={"request": RequestContext(self.user)}).data)

    @database_sync_to_async
    def _touch_presence(self):
        touch_presence(self.user.id)

    async def _broadcast_presence(self, status):
        for cid in self.conversation_ids:
            await self.channel_layer.group_send(
                f"conversation_{cid}",
                {"type": "chat.presence.update", "employee_id": str(self.user.id), "status": status},
            )
