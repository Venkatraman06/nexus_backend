from rest_framework import serializers

from apps.common.date_rules import validate_due_date_on_write

from .models import Todo


class TodoListSerializer(serializers.ModelSerializer):
    assignees_data = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")
    is_overdue = serializers.SerializerMethodField()
    can_transition = serializers.SerializerMethodField()
    allowed_destination_slugs = serializers.SerializerMethodField()

    class Meta:
        model = Todo
        fields = [
            "id", "title", "priority", "priority_label", "description", "content", "comments",
            "assignees", "assignees_data", "reporter", "reporter_name",
            "start_date", "due_date", "start_time", "end_time", "is_overdue",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "can_transition", "allowed_destination_slugs", "created_at", "updated_at",
        ]

    def get_assignees_data(self, obj):
        return [{"id": a.id, "full_name": a.full_name} for a in obj.assignees.all()]

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
        uid = user.pk
        return obj.reporter_id == uid or obj.assignees.filter(id=uid).exists()

    def get_allowed_destination_slugs(self, obj):
        request = self.context.get("request")
        if not request or not request.user:
            return []
        try:
            from .workflow import get_allowed_destination_slugs as _allowed_slugs
            return _allowed_slugs(obj, request.user)
        except Exception:
            return []


class TodoDetailSerializer(TodoListSerializer):
    available_states = serializers.SerializerMethodField()

    class Meta(TodoListSerializer.Meta):
        fields = TodoListSerializer.Meta.fields + ["available_states"]

    def get_available_states(self, obj):
        try:
            states = obj.get_available_next_states()
            return [
                {"id": str(s.id), "name": s.name, "slug": s.slug, "color": s.color_code}
                for s in states
            ]
        except Exception:
            return []


class TodoCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Todo
        fields = [
            "title", "priority", "description", "content", "comments",
            "assignees", "reporter", "start_date", "due_date", "start_time", "end_time",
        ]

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        if start and end and end <= start:
            raise serializers.ValidationError({"end_time": "End time must be after start time."})
        if "due_date" in attrs:
            validate_due_date_on_write(
                attrs.get("due_date"),
                previous_due_date=self.instance.due_date if self.instance else None,
                is_create=self.instance is None,
            )

        assignees = attrs.get("assignees", [])
        if not assignees and self.instance:
            assignees = list(self.instance.assignees.all())

        start_date = attrs.get("start_date") or attrs.get("due_date")
        if not start_date and self.instance:
            start_date = self.instance.start_date or self.instance.due_date

        if assignees and start_date:
            from .models import Todo
            from django.db.models import Q

            assignee_ids = [a.id if hasattr(a, 'id') else a for a in assignees]

            existing_qs = Todo.objects.filter(
                assignees__id__in=assignee_ids,
                is_deleted=False,
            ).filter(
                Q(start_date=start_date) | Q(due_date=start_date)
            ).exclude(
                workflow_state__slug__in=["completed", "cancelled"]
            ).distinct()

            if self.instance and self.instance.pk:
                existing_qs = existing_qs.exclude(pk=self.instance.pk)

            for existing in existing_qs:
                time_conflict = False
                if start and end and existing.start_time and existing.end_time:
                    if start < existing.end_time and end > existing.start_time:
                        time_conflict = True
                else:
                    time_conflict = True

                if time_conflict:
                    conflicting = existing.assignees.filter(id__in=assignee_ids)
                    names = ", ".join([a.full_name for a in conflicting]) or "An assignee"
                    task_title = existing.title or "a task"
                    raise serializers.ValidationError({
                        "assignees": f"Assignee {names} is already assigned to task '{task_title}' at this time on this day."
                    })

        return attrs


class CommentsUpdateSerializer(serializers.ModelSerializer):
    """Lightweight serializer for comment-only PATCH requests."""
    class Meta:
        model = Todo
        fields = ["comments"]


class TodoTransitionSerializer(serializers.Serializer):
    destination_state = serializers.CharField(required=True)
    comments = serializers.CharField(required=False, default="", allow_blank=True)
