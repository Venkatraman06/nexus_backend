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
    EmployeeMiniSerializer, ConversationListSerializer, ConversationDetailSerializer, ConversationCreateSerializer,
    MessageSerializer, MessageCreateSerializer, MessageUpdateSerializer,
    MessageAttachmentSerializer,
)
from .storage import get_chat_s3_storage


def _resolve_employee_by_str(emp_str):
    if not emp_str:
        return None
    from django.db.models import Q
    emp_str_clean = str(emp_str).strip()
    try:
        val_uuid = uuid.UUID(emp_str_clean)
        emp = Employee.objects.filter(id=val_uuid).first()
        if emp:
            return emp
    except Exception:
        pass
    emp = Employee.objects.filter(
        Q(employee_code__iexact=emp_str_clean) |
        Q(user__username__iexact=emp_str_clean) |
        Q(email__iexact=emp_str_clean) |
        Q(first_name__iexact=emp_str_clean)
    ).first()
    if not emp:
        for e in Employee.objects.filter(is_active=True):
            if emp_str_clean.lower() in str(e.id).lower() or emp_str_clean.lower() in str(e.employee_code).lower():
                return e
    return emp


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

    def list(self, request, *args, **kwargs):
        user = request.user
        # Auto-ensure permanent DIRECT conversation models exist between user and all employees
        all_emps = Employee.objects.exclude(id=user.id).filter(is_active=True)
        user_direct_conv_ids = set(
            ConversationParticipant.objects.filter(employee_id=user.id, conversation__type=ConversationType.DIRECT, conversation__is_deleted=False)
            .values_list("conversation_id", flat=True)
        )
        
        for emp in all_emps:
            other_direct_conv_ids = set(
                ConversationParticipant.objects.filter(employee_id=emp.id, conversation__type=ConversationType.DIRECT, conversation__is_deleted=False)
                .values_list("conversation_id", flat=True)
            )
            common = list(user_direct_conv_ids.intersection(other_direct_conv_ids))
            if not common:
                try:
                    with transaction.atomic():
                        new_conv = Conversation.objects.create(type=ConversationType.DIRECT, created_by=user, updated_by=user)
                        ConversationParticipant.objects.create(conversation=new_conv, employee_id=user.id, role=ParticipantRole.ADMIN, created_by=user, updated_by=user)
                        ConversationParticipant.objects.create(conversation=new_conv, employee_id=emp.id, role=ParticipantRole.MEMBER, created_by=user, updated_by=user)
                        user_direct_conv_ids.add(new_conv.id)
                except Exception:
                    pass

        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

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

        resolved_id = conversation_id
        if str(conversation_id).startswith("direct_"):
            target_emp_str = str(conversation_id).replace("direct_", "")
            target_emp = _resolve_employee_by_str(target_emp_str)
            if target_emp:
                existing = (
                    Conversation.objects.filter(type=ConversationType.DIRECT, is_deleted=False)
                    .filter(participants__employee_id=request.user.id)
                    .filter(participants__employee_id=target_emp.id)
                    .first()
                )
                if existing:
                    resolved_id = str(existing.id)
                else:
                    try:
                        from django.db import transaction
                        with transaction.atomic():
                            new_conv = Conversation.objects.create(type=ConversationType.DIRECT, created_by=request.user, updated_by=request.user)
                            ConversationParticipant.objects.create(conversation=new_conv, employee_id=request.user.id, role=ParticipantRole.ADMIN, created_by=request.user, updated_by=request.user)
                            ConversationParticipant.objects.create(conversation=new_conv, employee_id=target_emp.id, role=ParticipantRole.MEMBER, created_by=request.user, updated_by=request.user)
                            resolved_id = str(new_conv.id)
                    except Exception:
                        pass

        # Security check: verify that request.user is a participant in resolved_id or auto-add for DIRECT chats
        is_part = False
        if resolved_id and not str(resolved_id).startswith("direct_"):
            is_part = ConversationParticipant.objects.filter(conversation_id=resolved_id, employee_id=request.user.id).exists()
            if not is_part:
                conv_obj = Conversation.objects.filter(id=resolved_id).first()
                if conv_obj and conv_obj.type == ConversationType.DIRECT:
                    ConversationParticipant.objects.get_or_create(
                        conversation=conv_obj, employee_id=request.user.id,
                        defaults={"role": ParticipantRole.MEMBER, "created_by": request.user, "updated_by": request.user}
                    )
                    is_part = True
        else:
            is_part = True

        if not is_part:
            raise PermissionDenied("You do not have permission to view messages in this conversation.")

        messages = mongo.list_messages(
            resolved_id, is_important=_bool_param(request.query_params.get("is_important")),
        )
        if str(conversation_id).startswith("direct_") and resolved_id != conversation_id:
            extra_messages = mongo.list_messages(
                conversation_id, is_important=_bool_param(request.query_params.get("is_important")),
            )
            seen_ids = {m["_id"] for m in messages}
            for em in extra_messages:
                if em["_id"] not in seen_ids:
                    messages.append(em)
            messages.sort(key=lambda m: m.get("created_at", ""))

        serializer_data = self._serialize_many(messages)
        return Response(serializer_data)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        message = serializer.save()
        data = MessageSerializer(message, context=self.get_serializer_context()).data
        conv_id = data.get("conversation")
        raw_conv_id = request.data.get("conversation")
        
        # Sender has read up to their own sent message - update sender's last_read_at
        try:
            p = ConversationParticipant.objects.filter(conversation_id=conv_id, employee_id=request.user.id).first()
            if p:
                p.last_read_at = timezone.now()
                p.last_read_message_id = data.get("id")
                p.save(update_fields=["last_read_at", "last_read_message_id", "updated_at"])
        except Exception:
            pass

        broadcast_to_conversation(conv_id, "chat.message.created", data)
        if raw_conv_id and str(raw_conv_id) != str(conv_id):
            broadcast_to_conversation(str(raw_conv_id), "chat.message.created", data)
        return Response(data, status=status.HTTP_201_CREATED)

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
        msg_id = kwargs.get("pk")
        message = mongo.get_message_by_id(msg_id)
        if message is None:
            raise Http404
        if str(message.get("sender_id", "")).lower() != str(request.user.id).lower():
            raise PermissionDenied("Only the sender can delete this message.")
        updated = mongo.soft_delete_message(msg_id, request.user.id)
        if not updated:
            updated = message
            updated["is_deleted"] = True
        data = MessageSerializer(updated, context=self.get_serializer_context()).data
        conv_id = updated.get("conversation_id")
        broadcast_to_conversation(conv_id, "chat.message.deleted", data)
        return Response(data, status=status.HTTP_200_OK)

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

    @action(detail=True, methods=["post"], url_path="vote-poll")
    def vote_poll(self, request, pk=None):
        option_index = request.data.get("option_index")
        if option_index is None:
            raise ValidationError("option_index is required.")
        msg = mongo.vote_poll(pk, int(option_index), str(request.user.id))
        if not msg:
            raise Http404("Message or poll not found.")
        data = MessageSerializer(msg, context=self.get_serializer_context()).data
        broadcast_to_conversation(msg["conversation_id"], "chat.message.updated", data)
        return Response(data)

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


from .realtime import broadcast_to_conversation, broadcast_to_user

class CallViewSet(viewsets.ViewSet):
    permission_classes = [IsAuthenticated]

    def _broadcast_call_update(self, call_doc):
        if not call_doc:
            return
        conv_id = call_doc.get("conversation_id")
        if conv_id:
            broadcast_to_conversation(conv_id, "chat.call.update", call_doc)
        caller_id = call_doc.get("caller_id")
        recip_id = call_doc.get("recipient_id")
        if caller_id:
            broadcast_to_user(caller_id, "chat.call.update", call_doc)
        if recip_id:
            broadcast_to_user(recip_id, "chat.call.update", call_doc)

    @action(detail=False, methods=["post"])
    def initiate(self, request):
        recipient_id = request.data.get("recipient_id")
        call_type = request.data.get("call_type", "VOICE")
        conversation_id = request.data.get("conversation_id")
        if not recipient_id:
            return Response({"error": "recipient_id is required"}, status=status.HTTP_400_BAD_REQUEST)

        caller_id = str(request.user.id)
        call_doc = mongo.initiate_call(caller_id, recipient_id, call_type, conversation_id)

        caller_emp = Employee.objects.filter(id=caller_id).first()
        recip_emp = Employee.objects.filter(id=recipient_id).first()

        call_doc["caller"] = EmployeeMiniSerializer(caller_emp).data if caller_emp else None
        call_doc["recipient"] = EmployeeMiniSerializer(recip_emp).data if recip_emp else None

        self._broadcast_call_update(call_doc)

        return Response(call_doc, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def active(self, request):
        my_id = str(request.user.id)
        call_doc = mongo.get_active_call_for_user(my_id)
        if not call_doc:
            return Response(None)

        caller_emp = Employee.objects.filter(id=call_doc["caller_id"]).first()
        recip_emp = Employee.objects.filter(id=call_doc["recipient_id"]).first()

        call_doc["caller"] = EmployeeMiniSerializer(caller_emp).data if caller_emp else None
        call_doc["recipient"] = EmployeeMiniSerializer(recip_emp).data if recip_emp else None

        return Response(call_doc)

    @action(detail=False, methods=["post"])
    def respond(self, request):
        call_id = request.data.get("call_id")
        response_action = request.data.get("action")
        if not call_id or response_action not in ("ACCEPT", "DECLINE"):
            return Response({"error": "call_id and action (ACCEPT/DECLINE) required"}, status=status.HTTP_400_BAD_REQUEST)

        new_status = "ACCEPTED" if response_action == "ACCEPT" else "DECLINED"
        call_doc = mongo.update_call_status(call_id, new_status)
        self._broadcast_call_update(call_doc)
        return Response(call_doc)

    @action(detail=False, methods=["post"])
    def end(self, request):
        call_id = request.data.get("call_id")
        duration = int(request.data.get("duration_seconds", 0))
        if not call_id:
            return Response({"error": "call_id required"}, status=status.HTTP_400_BAD_REQUEST)

        call_doc = mongo.update_call_status(call_id, "ENDED", duration_seconds=duration)
        self._broadcast_call_update(call_doc)
        return Response(call_doc)

    @action(detail=False, methods=["get"])
    def history(self, request):
        my_id = str(request.user.id)
        history_list = mongo.list_call_history(my_id)

        emp_ids = set()
        for c in history_list:
            emp_ids.add(c["caller_id"])
            emp_ids.add(c["recipient_id"])

        employees = {str(e.id): EmployeeMiniSerializer(e).data for e in Employee.objects.filter(id__in=emp_ids)}

        for c in history_list:
            c["caller"] = employees.get(c["caller_id"])
            c["recipient"] = employees.get(c["recipient_id"])

        return Response(history_list)

