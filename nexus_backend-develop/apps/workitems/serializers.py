from decimal import Decimal

from rest_framework import serializers

from apps.timesheets.services import (
    assert_week_editable,
    assert_current_week_only,
    get_or_create_weekly_timesheet,
    link_work_log_to_week,
    refresh_weekly_totals,
    validate_work_log,
)

from .models import WorkLog


class WorkLogSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    ticket_id = serializers.CharField(source="ticket.ticket_id", read_only=True, default="")
    ticket_title = serializers.CharField(source="ticket.title", read_only=True, default="")
    project_name = serializers.CharField(source="ticket.project.name", read_only=True, default="")

    class Meta:
        model = WorkLog
        fields = [
            "id", "employee", "employee_name",
            "ticket", "ticket_id", "ticket_title", "project_name",
            "log_date", "hours", "description", "remarks",
            "category", "is_billable", "weekly_timesheet",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None


class WorkLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkLog
        fields = ["ticket", "log_date", "hours", "description", "remarks", "category"]

    def validate(self, attrs):
        request = self.context["request"]
        employee = request.user
        ticket = attrs.get("ticket") or (self.instance.ticket if self.instance else None)
        log_date = attrs.get("log_date") or (self.instance.log_date if self.instance else None)
        hours = attrs.get("hours")
        if hours is None and self.instance:
            hours = self.instance.hours

        if ticket and ticket.is_deleted:
            raise serializers.ValidationError({"ticket": "Cannot log time on a deleted ticket."})

        if not ticket:
            raise serializers.ValidationError({"ticket": "A ticket is required. Project-only logging is not allowed."})

        if log_date:
            assert_current_week_only(log_date)

        if self.instance and self.instance.weekly_timesheet:
            assert_week_editable(self.instance.weekly_timesheet)
        elif not self.instance and log_date:
            assert_week_editable(get_or_create_weekly_timesheet(employee, log_date))

        warnings = validate_work_log(
            employee=employee,
            ticket=ticket,
            log_date=log_date,
            hours=Decimal(str(hours)),
            work_log_id=self.instance.pk if self.instance else None,
        )
        self.context["validation_warnings"] = warnings
        return attrs

    def create(self, validated_data):
        validated_data["employee"] = self.context["request"].user
        validated_data["created_by"] = self.context["request"].user
        log = super().create(validated_data)
        link_work_log_to_week(log)
        log._validation_warnings = self.context.get("validation_warnings", {})
        return log

    def update(self, instance, validated_data):
        validated_data["updated_by"] = self.context["request"].user
        if instance.weekly_timesheet:
            assert_week_editable(instance.weekly_timesheet)
        log = super().update(instance, validated_data)
        if instance.weekly_timesheet:
            refresh_weekly_totals(instance.weekly_timesheet)
        else:
            link_work_log_to_week(log)
        log._validation_warnings = self.context.get("validation_warnings", {})
        return log

    def to_representation(self, instance):
        data = super().to_representation(instance)
        warnings = getattr(instance, "_validation_warnings", None)
        if warnings is None:
            warnings = self.context.get("validation_warnings", {})
        if warnings:
            data["warnings"] = warnings
        return data
