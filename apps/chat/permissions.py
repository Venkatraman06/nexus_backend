from rest_framework.permissions import BasePermission

from .models import ConversationParticipant


class IsConversationParticipant(BasePermission):
    """
    Object-level gate for chat: access to a conversation (or a message within
    one) requires an active ConversationParticipant row for the requesting
    employee. Chat has no Keycloak role boundary beyond "can use chat at all"
    (pmt.chat.view) — membership is what actually scopes access, matching how
    Teams/Slack authorize per-conversation.
    """

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        # obj is either a Conversation model instance, or a plain Mongo
        # message dict (apps/chat/mongo.py) — the latter has no `.conversation`.
        if isinstance(obj, dict):
            conversation_id = obj.get("conversation_id")
        elif hasattr(obj, "participants"):
            conversation_id = obj.id
        else:
            conversation_id = obj.conversation_id
        return ConversationParticipant.objects.filter(
            conversation_id=conversation_id, employee_id=request.user.id,
        ).exists()
