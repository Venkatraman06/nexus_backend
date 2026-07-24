from rest_framework import serializers

from apps.common.date_rules import validate_due_date_on_write

from .models import FollowUp


class FollowUpListSerializer(serializers.ModelSerializer):
    assignees_data = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    type_label = serializers.SerializerMethodField()
    priority_label = serializers.CharField(source="get_priority_display", read_only=True)

    def get_type_label(self, obj):
        from .models import FollowUpType
        for choice_val, choice_lbl in FollowUpType.choices:
            if choice_val == obj.type:
                return choice_lbl
        return obj.type.replace("_", " ").title() if obj.type else ""
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
            "description", "content", "comments",
            "assignees", "assignees_data", "reporter", "reporter_name",
            "start_date", "end_date", "start_time", "end_time", "is_overdue",
            "meeting_mode",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "can_transition", "allowed_destination_slugs", "created_at", "updated_at",
        ]

    def get_assignees_data(self, obj):
        return [{"id": a.id, "full_name": a.full_name} for a in obj.assignees.all()]

    def get_reporter_name(self, obj):
        return obj.reporter.full_name if obj.reporter else None

    def get_is_overdue(self, obj):
        from datetime import date, datetime
        if not obj.end_date:
            return False
        if obj.workflow_state and obj.workflow_state.is_final:
            return False
        end = obj.end_date
        if isinstance(end, str):
            try:
                end = datetime.strptime(end, "%Y-%m-%d").date()
            except ValueError:
                return False
        elif isinstance(end, datetime):
            end = end.date()
        return end < date.today()

    def get_can_transition(self, obj):
        request = self.context.get("request")
        if not request or not request.user:
            return False
        user = request.user
        if getattr(user, "is_superuser", False):
            return True
        user_perms = getattr(request, "user_permissions", [])
        if "pmt.crm.followup.view_all" in user_perms or "pmt.crm.followup.transition" in user_perms:
            return True
        uid = user.pk
        return (
            obj.reporter_id == uid or obj.created_by_id == uid or obj.assignees.filter(id=uid).exists()
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


class CommentsUpdateSerializer(serializers.ModelSerializer):
    """Lightweight serializer for comment-only PATCH requests."""
    class Meta:
        model = FollowUp
        fields = ["comments"]


class FollowUpCreateSerializer(serializers.ModelSerializer):
    description = serializers.CharField(required=True, allow_blank=False, error_messages={"blank": "Description is required."})
    start_date = serializers.DateField(required=True, allow_null=False, error_messages={"null": "Start date is required.", "required": "Start date is required."})
    end_date = serializers.DateField(required=True, allow_null=False, error_messages={"null": "End date is required.", "required": "End date is required."})

    class Meta:
        model = FollowUp
        fields = [
            "title", "type", "priority", "description", "content", "comments",
            "assignees", "reporter", "start_date", "end_date", "start_time", "end_time",
            "meeting_mode",
        ]

    def validate(self, attrs):
        start = attrs.get("start_time")
        end = attrs.get("end_time")
        start_date = attrs.get("start_date") or (self.instance.start_date if self.instance else None)
        end_date = attrs.get("end_date") or (self.instance.end_date if self.instance else None)

        if not start_date:
            raise serializers.ValidationError({"start_date": "Start date is required."})
        if not end_date:
            raise serializers.ValidationError({"end_date": "End date is required."})
        
        if start and end:
            # Only enforce time order if the follow-up starts and ends on the same day
            if start_date == end_date:
                if end <= start:
                    raise serializers.ValidationError({"end_time": "End time must be after start time."})
        if "end_date" in attrs:
            try:
                validate_due_date_on_write(
                    attrs.get("end_date"),
                    previous_due_date=self.instance.end_date if self.instance else None,
                    is_create=self.instance is None,
                )
            except serializers.ValidationError as e:
                if isinstance(e.detail, dict) and "due_date" in e.detail:
                    raise serializers.ValidationError({"end_date": e.detail["due_date"]})
                raise e

        # Conflict Validation: Check overlapping Meetings / Follow-ups for assignees
        start_time_val = attrs.get("start_time") if "start_time" in attrs else (self.instance.start_time if self.instance else None)
        end_time_val = attrs.get("end_time") if "end_time" in attrs else (self.instance.end_time if self.instance else None)

        assignees_val = attrs.get("assignees")
        if assignees_val is not None:
            assignee_ids = [a.id if hasattr(a, "id") else a for a in assignees_val]
        elif self.instance:
            assignee_ids = list(self.instance.assignees.values_list("id", flat=True))
        else:
            request = self.context.get("request")
            assignee_ids = [request.user.pk] if (request and request.user) else []

        if assignee_ids and start_date and end_date:
            from apps.followups.models import FollowUp
            from django.db.models import Q

            qs = FollowUp.objects.filter(is_deleted=False, assignees__id__in=assignee_ids)
            if self.instance:
                qs = qs.exclude(id=self.instance.id)

            # Date overlap check: candidate_start <= existing_end AND candidate_end >= existing_start
            qs = qs.filter(
                Q(start_date__lte=end_date, end_date__gte=start_date) |
                Q(start_date__isnull=True, end_date__gte=start_date, end_date__lte=end_date) |
                Q(end_date__isnull=True, start_date__gte=start_date, start_date__lte=end_date) |
                Q(start_date__isnull=True, end_date__isnull=True)
            ).prefetch_related("assignees").distinct()

            for item in qs:
                item_start = item.start_time
                item_end = item.end_time

                has_conflict = False
                if start_time_val and end_time_val and item_start and item_end:
                    # Interval overlap: new_start < existing_end AND new_end > existing_start
                    if start_time_val < item_end and end_time_val > item_start:
                        has_conflict = True
                else:
                    # If either event has no specific time bounds on overlapping date, treat as conflict
                    has_conflict = True

                if has_conflict:
                    time_info = ""
                    if item_start and item_end:
                        time_info = f" ({item_start.strftime('%I:%M %p')} - {item_end.strftime('%I:%M %p')})"
                    elif item_start:
                        time_info = f" ({item_start.strftime('%I:%M %p')})"
                    
                    item_kind = "Meeting" if item.type == "MEETING" else "Follow-up"
                    
                    err_msg = (
                        f"This assignee already has another Meeting or Follow-up scheduled during the "
                        f"selected date and time (Conflict with {item_kind} \"{item.title}\"{time_info}). "
                        f"Please choose a different time or assign another user."
                    )
                    raise serializers.ValidationError(err_msg)

        return attrs


class FollowUpTransitionSerializer(serializers.Serializer):
    destination_state = serializers.CharField(required=True)
    comments = serializers.CharField(required=False, default="", allow_blank=True)
