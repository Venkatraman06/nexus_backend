from rest_framework import serializers

from .models import FollowUp


class FollowUpListSerializer(serializers.ModelSerializer):
    assignee_name = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    type_label = serializers.CharField(source="get_type_display", read_only=True)
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")
    is_overdue = serializers.SerializerMethodField()
    can_transition = serializers.SerializerMethodField()
    allowed_destination_slugs = serializers.SerializerMethodField()

    class Meta:
        model = FollowUp
        fields = [
            "id", "title", "type", "type_label", "priority", "priority_label",
            "description", "comments",
            "assignee", "assignee_name", "reporter", "reporter_name",
            "due_date", "start_time", "end_time", "is_overdue",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "can_transition", "allowed_destination_slugs", "created_at", "updated_at",
        ]

    def get_assignee_name(self, obj):
        return obj.assignee.full_name if obj.assignee else None

    def get_reporter_name(self, obj):
        return obj.reporter.full_name if obj.reporter else None

    def get_is_overdue(self, obj):
        from datetime import date
        if not obj.due_date:
            return False
        if obj.workflow_state and obj.workflow_state.is_final:
            return False
        return obj.due_date < date.today()

    def get_can_transition(self, obj):
        request = self.context.get("request")
        if not request or not request.user:
            return False
        user = request.user
        if getattr(user, "is_superuser", False):
            return True
        user_perms = getattr(request, "user_permissions", [])
        if "pmt.crm.followup.view_all" in user_perms:
            return True
        uid = user.pk
        return (
            (obj.assignee_id == uid or obj.reporter_id == uid)
        )

    def get_allowed_destination_slugs(self, obj):
        request = self.context.get("request")
        if not request or not request.user:
            return []
        try:
            from .workflow import get_allowed_destination_slugs as _allowed_slugs
            return _allowed_slugs(obj, request.user)
        except Exception:
            return []


class FollowUpDetailSerializer(FollowUpListSerializer):
    available_states = serializers.SerializerMethodField()

    class Meta(FollowUpListSerializer.Meta):
        fields = FollowUpListSerializer.Meta.fields + ["available_states"]

    def get_available_states(self, obj):
        try:
            states = obj.get_available_next_states()
            return [
                {"id": str(s.id), "name": s.name, "slug": s.slug, "color": s.color_code}
                for s in states
            ]
        except Exception:
            return []


class FollowUpCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowUp
        fields = [
            "title", "type", "priority", "description", "comments",
            "assignee", "reporter", "due_date", "start_time", "end_time",
        ]

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        return attrs


class FollowUpTransitionSerializer(serializers.Serializer):
    destination_state = serializers.CharField(required=True)
    comments = serializers.CharField(required=False, default="", allow_blank=True)
