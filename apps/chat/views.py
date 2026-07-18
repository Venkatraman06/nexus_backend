import uuid

from django.conf import settings
from django.http import Http404
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Employee
from apps.common.viewsets import BaseModelViewSet
from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from apps.common.response import CommonResponseMixin
from . import mongo
from .models import (
    Conversation, ConversationParticipant, ConversationType, ParticipantRole,
    ConversationAuditLog,
)
from .permissions import IsConversationParticipant
from .realtime import broadcast_to_conversation
from .serializers import (
    ConversationListSerializer, ConversationDetailSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer, MessageUpdateSerializer,
    MessageAttachmentSerializer,
)
from .storage import get_chat_s3_storage


class ConversationViewSet(BaseModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission, IsConversationParticipant]
    ordering = ["-last_message_at"]

    PERMISSION_MAP = {
        "list": "pmt.chat.view",
        "retrieve": "pmt.chat.view",
        "create": "pmt.chat.view",
        "update": "pmt.chat.view",
        "partial_update": "pmt.chat.view",
        "destroy": "pmt.chat.view",
        "favorite": "pmt.chat.view",
        "read": "pmt.chat.view",
        "members": "pmt.chat.view",
        "remove_member": "pmt.chat.view",
        "presign_attachment": "pmt.chat.view",
    }

    def get_queryset(self):
        return (
            Conversation.objects.filter(is_deleted=False, participants__employee_id=self.request.user.id)
            .prefetch_related("participants__employee")
            .distinct()
        )

    def get_serializer_class(self):
        if self.action == "create":
            return ConversationCreateSerializer
        if self.action == "retrieve":
            return ConversationDetailSerializer
        return ConversationListSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        conversation = serializer.save(created_by=request.user, updated_by=request.user)
        return Response(
            ConversationDetailSerializer(conversation, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def _my_participant(self, conversation):
        return ConversationParticipant.objects.filter(
            conversation=conversation, employee_id=self.request.user.id,
        ).first()

    def _require_admin(self, conversation, participant):
        if conversation.type != ConversationType.GROUP:
            raise ValidationError("Only group conversations support membership changes.")
        if participant is None or participant.role != ParticipantRole.ADMIN:
            raise PermissionDenied("Only a group admin can manage members.")

    def destroy(self, request, *args, **kwargs):
        conversation = self.get_object()
        participant = self._my_participant(conversation)
        self._require_admin(conversation, participant)
        conversation.soft_delete(user=request.user)
        return Response(status=status.HTTP_204_NO_CONTENT)

    def update(self, request, *args, **kwargs):
        # Renaming / changing the group photo is an admin action — 1:1
        # conversations have nothing user-editable here (name/avatar aren't
        # displayed for DIRECT type; the frontend derives those from the
        # other participant instead), so there's no path that reaches this
        # for them today, but the check is defensive either way.
        conversation = self.get_object()
        if conversation.type == ConversationType.GROUP:
            participant = self._my_participant(conversation)
            if participant is None or participant.role != ParticipantRole.ADMIN:
                raise PermissionDenied("Only a group admin can update group info.")
        return super().update(request, *args, **kwargs)

    @action(detail=True, methods=["post"], url_path="attachments/presign")
    def presign_attachment(self, request, pk=None):
        conversation = self.get_object()  # 404s if not a participant
        filename = request.data.get("filename")
        content_type = request.data.get("content_type") or "application/octet-stream"
        size_bytes = request.data.get("size_bytes")
        if not filename or size_bytes is None:
            raise ValidationError("filename and size_bytes are required.")
        if int(size_bytes) > settings.CHAT_MAX_ATTACHMENT_SIZE:
            raise ValidationError(
                f"File exceeds the {settings.CHAT_MAX_ATTACHMENT_SIZE} byte limit."
            )

        object_key = f"chat/{conversation.id}/{uuid.uuid4()}-{filename}"
        upload_url = get_chat_s3_storage().generate_presigned_put_url(object_key, content_type)
        return Response({"upload_url": upload_url, "object_key": object_key})

    @action(detail=True, methods=["post"])
    def favorite(self, request, pk=None):
        conversation = self.get_object()
        participant = self._my_participant(conversation)
        if participant is None:
            raise PermissionDenied("Not a participant of this conversation.")
        participant.is_favorite = not participant.is_favorite
        participant.save(update_fields=["is_favorite", "updated_at"])
        return Response({"is_favorite": participant.is_favorite})

    @action(detail=True, methods=["post"])
    def read(self, request, pk=None):
        conversation = self.get_object()
        participant = self._my_participant(conversation)
        if participant is None:
            raise PermissionDenied("Not a participant of this conversation.")
        latest = mongo.last_message_for(conversation.id)
        participant.last_read_message_id = latest["_id"] if latest else None
        participant.last_read_at = timezone.now()
        participant.save(update_fields=["last_read_message_id", "last_read_at", "updated_at"])
        return Response({"last_read_at": participant.last_read_at})

    @action(detail=True, methods=["post"])
    def members(self, request, pk=None):
        conversation = self.get_object()
        participant = self._my_participant(conversation)
        self._require_admin(conversation, participant)

        employee_ids = request.data.get("employee_ids") or []
        if not employee_ids:
            raise ValidationError("employee_ids is required.")

        existing = set(
            conversation.participants.values_list("employee_id", flat=True).distinct()
        )
        created = []
        for eid in employee_ids:
            if str(eid) in {str(e) for e in existing}:
                continue
            created.append(ConversationParticipant(
                conversation=conversation, employee_id=eid,
                role=ParticipantRole.MEMBER,
                created_by=request.user, updated_by=request.user,
            ))
        ConversationParticipant.objects.bulk_create(created)
        for eid in employee_ids:
            ConversationAuditLog.objects.create(
                conversation=conversation, actor=request.user,
                action="member_added", target_employee_id=eid,
            )
        # `conversation` was fetched via get_object(), which prefetches
        # participants__employee — that cache predates the bulk_create above,
        # so serializing it directly would still show the old member list.
        conversation.refresh_from_db()
        return Response(ConversationDetailSerializer(conversation, context=self.get_serializer_context()).data)

    @action(detail=True, methods=["delete"], url_path="members/(?P<employee_id>[^/.]+)")
    def remove_member(self, request, pk=None, employee_id=None):
        conversation = self.get_object()
        participant = self._my_participant(conversation)
        is_self_leave = str(request.user.id) == str(employee_id)
        if not is_self_leave:
            self._require_admin(conversation, participant)
        elif conversation.type != ConversationType.GROUP:
            raise ValidationError("Only group conversations can be left.")

        target = conversation.participants.filter(employee_id=employee_id).first()
        if target is None:
            return Response(status=status.HTTP_404_NOT_FOUND)
        target.delete()
        ConversationAuditLog.objects.create(
            conversation=conversation, actor=request.user,
            action="member_left" if is_self_leave else "member_removed",
            target_employee_id=employee_id,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


def _bool_param(value):
    if value is None:
        return None
    return value.lower() in ("1", "true", "yes")


class MessageViewSet(CommonResponseMixin, viewsets.GenericViewSet):
    """
    Messages live in MongoDB (apps/chat/mongo.py), not Postgres — this is a
    plain GenericViewSet (not ModelViewSet) since there's no Django queryset
    to hang the usual mixins off of. Pagination still works: DRF's paginator
    only needs len()/slicing, which a plain Python list already supports.
    """
    permission_classes = [IsAuthenticated, HasKeycloakPermission, IsConversationParticipant]

    PERMISSION_MAP = {
        "list": "pmt.chat.view",
        "retrieve": "pmt.chat.view",
        "create": "pmt.chat.view",
        "update": "pmt.chat.view",
        "partial_update": "pmt.chat.view",
        "destroy": "pmt.chat.view",
        "star": "pmt.chat.view",
        "mark_important": "pmt.chat.view",
        "mentions": "pmt.chat.view",
        "starred": "pmt.chat.view",
    }

    def get_serializer_class(self):
        if self.action == "create":
            return MessageCreateSerializer
        if self.action in ("update", "partial_update"):
            return MessageUpdateSerializer
        return MessageSerializer

    def _sender_lookup(self, messages):
        ids = {m["sender_id"] for m in messages if m.get("sender_id")}
        if not ids:
            return {}
        return {str(e.id): e for e in Employee.objects.filter(id__in=ids)}

    def _serialize_many(self, messages):
        senders = self._sender_lookup(messages)
        return MessageSerializer(
            messages, many=True, context={**self.get_serializer_context(), "senders": senders},
        ).data

    def _get_message_or_404(self, message_id):
        message = mongo.get_message(message_id)
        if message is None:
            raise Http404
        self.check_object_permissions(self.request, message)
        return message

    def list(self, request, *args, **kwargs):
        conversation_id = request.query_params.get("conversation")
        if not conversation_id:
            raise ValidationError({"conversation": "This query parameter is required."})
        if not ConversationParticipant.objects.filter(
            conversation_id=conversation_id, employee_id=request.user.id,
        ).exists():
            raise Http404

        messages = mongo.list_messages(
            conversation_id, is_important=_bool_param(request.query_params.get("is_important")),
        )
        page = self.paginate_queryset(messages)
        serializer_data = self._serialize_many(page if page is not None else messages)
        if page is not None:
            return self.get_paginated_response(serializer_data)
        return Response(serializer_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        return Response(
            MessageSerializer(message, context=self.get_serializer_context()).data,
            status=status.HTTP_201_CREATED,
        )

    def retrieve(self, request, *args, **kwargs):
        message = self._get_message_or_404(kwargs["pk"])
        return Response(MessageSerializer(message, context=self.get_serializer_context()).data)

    def update(self, request, *args, **kwargs):
        partial = kwargs.get("partial", False)
        message = self._get_message_or_404(kwargs["pk"])
        if message["sender_id"] != str(request.user.id):
            raise PermissionDenied("Only the sender can edit this message.")
        if message["is_deleted"]:
            raise ValidationError("A deleted message cannot be edited.")
        serializer = self.get_serializer(message, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        updated = serializer.save()
        data = MessageSerializer(updated, context=self.get_serializer_context()).data
        broadcast_to_conversation(updated["conversation_id"], "chat.message.updated", data)
        return Response(data)

    def partial_update(self, request, *args, **kwargs):
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        message = self._get_message_or_404(kwargs["pk"])
        if message["sender_id"] != str(request.user.id):
            raise PermissionDenied("Only the sender can delete this message.")
        updated = mongo.soft_delete_message(message["_id"], request.user.id)
        data = MessageSerializer(updated, context=self.get_serializer_context()).data
        broadcast_to_conversation(updated["conversation_id"], "chat.message.deleted", data)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"])
    def star(self, request, pk=None):
        message = self._get_message_or_404(pk)
        starred = mongo.toggle_star(message["_id"], request.user.id)
        return Response({"is_starred_by_me": starred})

    @action(detail=True, methods=["post"], url_path="important")
    def mark_important(self, request, pk=None):
        message = self._get_message_or_404(pk)
        updated = mongo.toggle_important(message["_id"], request.user.id)
        return Response({"is_important": updated["is_important"]})

    @action(detail=False, methods=["get"])
    def mentions(self, request):
        conversation_ids = list(
            ConversationParticipant.objects.filter(employee_id=request.user.id).values_list("conversation_id", flat=True)
        )
        messages = mongo.mentions_for(request.user.id, conversation_ids)
        page = self.paginate_queryset(messages)
        data = self._serialize_many(page if page is not None else messages)
        return self.get_paginated_response(data) if page is not None else Response(data)

    @action(detail=False, methods=["get"])
    def starred(self, request):
        conversation_ids = list(
            ConversationParticipant.objects.filter(employee_id=request.user.id).values_list("conversation_id", flat=True)
        )
        messages = mongo.starred_for(request.user.id, conversation_ids)
        page = self.paginate_queryset(messages)
        data = self._serialize_many(page if page is not None else messages)
        return self.get_paginated_response(data) if page is not None else Response(data)


class ChatSearchView(CommonResponseMixin, APIView):
    """
    Global or in-chat search across message bodies and attachment filenames
    (MongoDB substring match — see apps/chat/mongo.py::search_messages) —
    powers the "My Mentions"/"Important"/"Files"-style filtered views
    client-side, plus a general search box.

    ?q=<term>&conversation=<id optional>
    """
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    required_permission = "pmt.chat.view"

    def get(self, request):
        query = request.query_params.get("q", "").strip()
        if not query:
            raise ValidationError({"q": "This query parameter is required."})
        conversation_id = request.query_params.get("conversation")

        conversation_ids = list(
            ConversationParticipant.objects.filter(employee_id=request.user.id).values_list("conversation_id", flat=True)
        )
        results = mongo.search_messages(query, conversation_ids, conversation_id=conversation_id)

        sender_ids = {m["sender_id"] for m in results["messages"] if m.get("sender_id")}
        senders = {str(e.id): e for e in Employee.objects.filter(id__in=sender_ids)} if sender_ids else {}

        matching_files = []
        needle = query.lower()
        for message in results["files"]:
            for attachment in message.get("attachments", []):
                if needle in attachment["original_filename"].lower():
                    data = MessageAttachmentSerializer(attachment).data
                    data["message_id"] = message["_id"]
                    matching_files.append(data)

        return Response({
            "messages": MessageSerializer(
                results["messages"], many=True, context={"request": request, "senders": senders},
            ).data,
            "files": matching_files,
        })
