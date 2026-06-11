from rest_framework import serializers

from apps.workitems.models import WorkLog
from apps.workitems.serializers import WorkLogSerializer

from apps.common.constants import TimesheetStatus, WorkLogCategory

from .models import TimesheetConfig, WeeklyTimesheet
from .services import ticket_hierarchy


class WeeklyTimesheetSerializer(serializers.ModelSerializer):
    employee_name = serializers.CharField(source="employee.full_name", read_only=True)
    hours_behind = serializers.SerializerMethodField()

    class Meta:
        model = WeeklyTimesheet
        fields = [
            "id", "employee", "employee_name",
            "week_start", "week_end", "status",
            "total_hours", "expected_hours", "hours_behind",
            "submitted_at", "reviewed_at", "reviewed_by", "review_comment",
        ]

    def get_hours_behind(self, obj):
        behind = float(obj.expected_hours) - float(obj.total_hours)
        return max(0, round(behind, 2))


class WorkLogDetailSerializer(WorkLogSerializer):
    project_id = serializers.CharField(source="ticket.project_id", read_only=True, default="")
    project_name = serializers.CharField(source="ticket.project.name", read_only=True, default="")
    ticket_type = serializers.CharField(source="ticket.type", read_only=True, default="")
    epic_title = serializers.SerializerMethodField()
    story_title = serializers.SerializerMethodField()
    warnings = serializers.SerializerMethodField()

    class Meta(WorkLogSerializer.Meta):
        fields = WorkLogSerializer.Meta.fields + [
            "project_id", "ticket_type", "epic_title", "story_title",
            "description", "category", "weekly_timesheet", "warnings",
        ]

    def get_epic_title(self, obj):
        if not obj.ticket:
            return ""
        return ticket_hierarchy(obj.ticket)["epic_title"]

    def get_story_title(self, obj):
        if not obj.ticket:
            return ""
        return ticket_hierarchy(obj.ticket)["story_title"]

    def get_warnings(self, obj):
        return getattr(obj, "_validation_warnings", {})


class LoggableTicketSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    ticket_id = serializers.CharField()
    title = serializers.CharField()
    type = serializers.CharField()
    project_id = serializers.UUIDField()
    project_name = serializers.CharField()
    epic_title = serializers.CharField()
    story_title = serializers.CharField()


class TimesheetWeekSerializer(serializers.Serializer):
    weekly_timesheet = WeeklyTimesheetSerializer()
    days = serializers.ListField()
    logs = WorkLogDetailSerializer(many=True)
    daily_capacity = serializers.DecimalField(max_digits=4, decimal_places=2)


class SubmitTimesheetSerializer(serializers.Serializer):
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class ReviewTimesheetSerializer(serializers.Serializer):
    timesheet_id = serializers.UUIDField()
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class BulkReviewSerializer(serializers.Serializer):
    timesheet_ids = serializers.ListField(child=serializers.UUIDField(), min_length=1)
    comment = serializers.CharField(required=False, allow_blank=True, default="")


class CopyDaySerializer(serializers.Serializer):
    source_date = serializers.DateField()
    target_date = serializers.DateField()


class CopyWeekSerializer(serializers.Serializer):
    source_week_start = serializers.DateField()
    target_week_start = serializers.DateField()


class TimesheetConfigSerializer(serializers.ModelSerializer):
    class Meta:
        model = TimesheetConfig
        fields = ["id", "daily_capacity_hours"]


class WorkLogCategoryField(serializers.ChoiceField):
    def __init__(self, **kwargs):
        super().__init__(choices=WorkLogCategory.choices, **kwargs)
