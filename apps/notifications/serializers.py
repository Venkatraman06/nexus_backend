from rest_framework import serializers

from apps.notifications.models import Notification


class NotificationSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()

    class Meta:
        model = Notification
        fields = [
            "id", "event_type", "title", "message",
            "reference_type", "reference_id", "action_url",
            "severity", "is_read", "read_at",
            "actor_name", "metadata", "created_at",
        ]
        read_only_fields = fields

    def get_actor_name(self, obj):
        return obj.actor.full_name if obj.actor else None


class MarkReadSerializer(serializers.Serializer):
    ids = serializers.ListField(
        child=serializers.UUIDField(),
        required=False,
        allow_empty=True,
    )
