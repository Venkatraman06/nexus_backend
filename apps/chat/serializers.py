from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import Employee
from . import mongo
from .models import (
    Conversation, ConversationParticipant, ConversationType, ParticipantRole,
)

SCAN_PENDING, SCAN_CLEAN, SCAN_INFECTED, SCAN_ERROR = "PENDING", "CLEAN", "INFECTED", "ERROR"


class EmployeeMiniSerializer(serializers.ModelSerializer):
    profile_picture_url = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = ["id", "full_name", "email", "profile_picture_url"]

    def get_profile_picture_url(self, obj):
        try:
            return obj.profile_picture.url if obj.profile_picture else None
        except ValueError:
            return None


class MessageAttachmentSerializer(serializers.Serializer):
    id = serializers.CharField()
    original_filename = serializers.CharField()
    content_type = serializers.CharField()
    size_bytes = serializers.IntegerField()
    scan_status = serializers.CharField()
    scanned_at = serializers.DateTimeField(allow_null=True)
    download_url = serializers.SerializerMethodField()

    def get_download_url(self, obj):
        # Withheld until ClamAV has cleared the file — see apps/chat/tasks.py.
        if obj.get("scan_status") != SCAN_CLEAN:
            return None
        from .storage import get_chat_s3_storage
        return get_chat_s3_storage().get_presigned_url(obj["object_key"])


class AttachmentInputSerializer(serializers.Serializer):
    object_key = serializers.CharField()
    original_filename = serializers.CharField()
    content_type = serializers.CharField(required=False, allow_blank=True, default="")
    size_bytes = serializers.IntegerField(min_value=0)


class ConversationParticipantSerializer(serializers.ModelSerializer):
    employee = EmployeeMiniSerializer(read_only=True)

    class Meta:
        model = ConversationParticipant
        fields = ["id", "employee", "role", "is_favorite", "muted", "last_read_at"]


class ConversationListSerializer(serializers.ModelSerializer):
    participants = ConversationParticipantSerializer(many=True, read_only=True)
    unread_count = serializers.SerializerMethodField()
    is_favorite = serializers.SerializerMethodField()
    last_message_preview = serializers.SerializerMethodField()
    avatar_url = serializers.SerializerMethodField()
    # `avatar` stores a MinIO object key (uploaded via the same presign flow
    # as message attachments), not a browsable URL — write-only so clients
    # only ever see the presigned `avatar_url` for display.
    avatar = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Conversation
        fields = [
            "id", "type", "name", "avatar", "avatar_url", "is_archived", "last_message_at",
            "participants", "unread_count", "is_favorite", "last_message_preview",
        ]

    def get_avatar_url(self, obj):
        if not obj.avatar:
            return None
        from .storage import get_chat_s3_storage
        return get_chat_s3_storage().get_presigned_url(obj.avatar)

    def _my_participant(self, obj):
        user = self.context["request"].user
        for p in obj.participants.all():
            if p.employee_id == user.id:
                return p
        return None

    def get_unread_count(self, obj):
        participant = self._my_participant(obj)
        if participant is None:
            return 0
        return mongo.unread_count(obj.id, participant.last_read_at, participant.employee_id)

    def get_is_favorite(self, obj):
        participant = self._my_participant(obj)
        return bool(participant and participant.is_favorite)

    def get_last_message_preview(self, obj):
        last = mongo.last_message_for(obj.id)
        if not last:
            return None
        from .text import strip_html_preview
        return {
            "body": strip_html_preview(last["body"], length=200),
            "sender_id": last["sender_id"],
            "created_at": last["created_at"],
        }


class ConversationDetailSerializer(ConversationListSerializer):
    class Meta(ConversationListSerializer.Meta):
        pass


class ConversationCreateSerializer(serializers.ModelSerializer):
    participant_ids = serializers.ListField(
        child=serializers.UUIDField(), write_only=True, allow_empty=False,
    )

    class Meta:
        model = Conversation
        fields = ["id", "type", "name", "avatar", "participant_ids"]

    def validate(self, attrs):
        participant_ids = set(str(pid) for pid in attrs["participant_ids"])
        if attrs["type"] == ConversationType.DIRECT and len(participant_ids) != 1:
            raise serializers.ValidationError(
                "Direct conversations require exactly one other participant."
            )
        if attrs["type"] == ConversationType.GROUP and not attrs.get("name"):
            raise serializers.ValidationError("Group conversations require a name.")
        return attrs

    @transaction.atomic
    def create(self, validated_data):
        participant_ids = validated_data.pop("participant_ids")
        request = self.context["request"]
        creator = request.user
        # BaseModelViewSet.perform_create injects these into validated_data;
        # pop rather than pass explicitly below to avoid a duplicate kwarg.
        validated_data.pop("created_by", None)
        validated_data.pop("updated_by", None)

        if validated_data["type"] == ConversationType.DIRECT:
            other_id = participant_ids[0]
            existing = (
                Conversation.objects.filter(type=ConversationType.DIRECT, is_deleted=False)
                .filter(participants__employee_id=creator.id)
                .filter(participants__employee_id=other_id)
                .first()
            )
            if existing:
                return existing

        conversation = Conversation.objects.create(
            created_by=creator, updated_by=creator, **validated_data,
        )
        all_ids = set(participant_ids) | {creator.id}
        ConversationParticipant.objects.bulk_create([
            ConversationParticipant(
                conversation=conversation,
                employee_id=pid,
                role=ParticipantRole.ADMIN if str(pid) == str(creator.id) else ParticipantRole.MEMBER,
                created_by=creator, updated_by=creator,
            )
            for pid in all_ids
        ])
        return conversation


class MessageSerializer(serializers.Serializer):
    """
    Reads a Mongo message document (plain dict — see apps/chat/mongo.py) into
    the same JSON shape the frontend already expects. `context["senders"]`
    may hold a pre-fetched {employee_id: Employee} map (list views, avoids
    one query per message) — falls back to a single query otherwise.
    """
    id = serializers.CharField(source="_id")
    conversation = serializers.CharField(source="conversation_id")
    sender = serializers.SerializerMethodField()
    body = serializers.SerializerMethodField()
    reply_to = serializers.CharField(allow_null=True)
    is_edited = serializers.BooleanField()
    edited_at = serializers.DateTimeField(allow_null=True)
    is_important = serializers.BooleanField()
    is_deleted = serializers.BooleanField()
    mentioned_employee_ids = serializers.SerializerMethodField()
    attachments = serializers.SerializerMethodField()
    is_starred_by_me = serializers.SerializerMethodField()
    reaction_summary = serializers.SerializerMethodField()
    created_at = serializers.DateTimeField()
    updated_at = serializers.DateTimeField()

    def get_body(self, obj):
        return "This message was deleted" if obj.get("is_deleted") else obj.get("body", "")

    def get_mentioned_employee_ids(self, obj):
        return [] if obj.get("is_deleted") else obj.get("mentions", [])

    def get_attachments(self, obj):
        if obj.get("is_deleted"):
            return []
        return MessageAttachmentSerializer(obj.get("attachments", []), many=True).data

    def get_is_starred_by_me(self, obj):
        user = self.context["request"].user
        return str(user.id) in obj.get("stars", [])

    def get_reaction_summary(self, obj):
        summary: dict[str, list[str]] = {}
        for reaction in obj.get("reactions", []):
            summary.setdefault(reaction["emoji"], []).append(reaction["employee_id"])
        return summary

    def get_sender(self, obj):
        sender_id = obj.get("sender_id")
        if not sender_id:
            return None
        senders = self.context.get("senders")
        employee = senders.get(sender_id) if senders is not None else Employee.objects.filter(id=sender_id).first()
        return EmployeeMiniSerializer(employee).data if employee else None


class MessageCreateSerializer(serializers.Serializer):
    conversation = serializers.PrimaryKeyRelatedField(queryset=Conversation.objects.filter(is_deleted=False))
    body = serializers.CharField(allow_blank=True, default="")
    reply_to = serializers.CharField(required=False, allow_null=True, default=None)
    is_important = serializers.BooleanField(required=False, default=False)
    mention_employee_ids = serializers.ListField(
        child=serializers.UUIDField(), required=False, default=list,
    )
    attachments = AttachmentInputSerializer(many=True, required=False, default=list)

    def validate_conversation(self, conversation):
        user = self.context["request"].user
        if not ConversationParticipant.objects.filter(
            conversation=conversation, employee_id=user.id,
        ).exists():
            raise serializers.ValidationError("You are not a participant of this conversation.")
        return conversation

    def validate_attachments(self, attachments):
        from django.conf import settings
        for item in attachments:
            if item["size_bytes"] > settings.CHAT_MAX_ATTACHMENT_SIZE:
                raise serializers.ValidationError(
                    f"{item['original_filename']} exceeds the {settings.CHAT_MAX_ATTACHMENT_SIZE} byte limit."
                )
        return attachments

    def create(self, validated_data):
        request = self.context["request"]
        conversation = validated_data["conversation"]
        attachment_inputs = validated_data.get("attachments") or []
        attachments = [
            {
                "id": mongo.new_id(),
                "object_key": item["object_key"],
                "original_filename": item["original_filename"],
                "content_type": item.get("content_type", ""),
                "size_bytes": item["size_bytes"],
                "scan_status": SCAN_PENDING,
                "scanned_at": None,
            }
            for item in attachment_inputs
        ]

        message = mongo.create_message(
            conversation_id=conversation.id,
            sender_id=request.user.id,
            body=validated_data.get("body", ""),
            reply_to=validated_data.get("reply_to"),
            is_important=validated_data.get("is_important", False),
            mentions=validated_data.get("mention_employee_ids") or [],
            attachments=attachments,
        )

        if attachments:
            from .tasks import scan_attachment
            for attachment in attachments:
                transaction.on_commit(lambda aid=attachment["id"]: scan_attachment.delay(str(message["_id"]), aid))

        conversation.last_message_at = timezone.now()
        conversation.save(update_fields=["last_message_at"])

        from .notify import notify_new_message
        from .realtime import broadcast_to_conversation
        transaction.on_commit(lambda: notify_new_message(message, request.user))
        transaction.on_commit(lambda: broadcast_to_conversation(
            message["conversation_id"], "chat.message.new",
            MessageSerializer(message, context=self.context).data,
        ))

        return message


class MessageUpdateSerializer(serializers.Serializer):
    body = serializers.CharField()

    def update(self, instance, validated_data):
        return mongo.update_message_body(instance["_id"], validated_data["body"], self.context["request"].user.id)
