from rest_framework import serializers

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
            "log_date", "hours", "remarks", "is_billable",
            "created_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None


class WorkLogCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkLog
        fields = ["ticket", "log_date", "hours", "remarks", "is_billable"]

    def validate(self, attrs):
        ticket = attrs.get("ticket")
        if ticket and ticket.is_deleted:
            raise serializers.ValidationError("Cannot log time on a deleted ticket.")
        return attrs

    def create(self, validated_data):
        validated_data["employee"] = self.context["request"].user
        return super().create(validated_data)
