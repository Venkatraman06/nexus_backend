from rest_framework import serializers

from .models import (
    OffboardingRecord, OffboardingPreference, ClearanceItem,
    ExitInterview, OffboardingDocument, OffboardingWorkflowStage,
)


def _name(user):
    if not user:
        return None
    return getattr(user, "full_name", None) or str(user)


class OffboardingPreferenceSerializer(serializers.ModelSerializer):
    class Meta:
        model = OffboardingPreference
        fields = [
            "id", "offboarding", "preferred_last_working_day",
            "reason_for_leaving", "will_serve_notice_period",
            "feedback", "remarks", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "offboarding", "created_at", "updated_at"]


class ClearanceItemSerializer(serializers.ModelSerializer):
    cleared_by_name = serializers.SerializerMethodField()

    class Meta:
        model = ClearanceItem
        fields = [
            "id", "offboarding", "department", "item_name",
            "is_cleared", "cleared_by", "cleared_by_name",
            "cleared_date", "remarks", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "offboarding", "cleared_by_name", "created_at", "updated_at"]

    def get_cleared_by_name(self, obj):
        return _name(obj.cleared_by)


class ExitInterviewSerializer(serializers.ModelSerializer):
    interviewer_name = serializers.SerializerMethodField()

    class Meta:
        model = ExitInterview
        fields = [
            "id", "offboarding", "interview_date", "interviewer", "interviewer_name",
            "notes", "rating", "would_recommend", "is_completed",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "offboarding", "interviewer_name", "created_at", "updated_at"]

    def get_interviewer_name(self, obj):
        return _name(obj.interviewer)


class OffboardingDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(
        source="get_document_type_display", read_only=True
    )

    class Meta:
        model = OffboardingDocument
        fields = [
            "id", "offboarding", "document_type", "document_type_display",
            "title", "file", "file_url", "uploaded_by", "uploaded_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "file_url", "uploaded_by", "uploaded_by_name",
            "document_type_display", "created_at", "updated_at",
        ]

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None

    def get_uploaded_by_name(self, obj):
        return _name(obj.uploaded_by)


class OffboardingWorkflowStageSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = OffboardingWorkflowStage
        fields = [
            "id", "offboarding", "stage_name", "order", "status",
            "assigned_to", "assigned_to_name", "completed_date",
            "remarks", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "offboarding", "assigned_to_name", "created_at", "updated_at"]

    def get_assigned_to_name(self, obj):
        return _name(obj.assigned_to)


class OffboardingRecordSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    initiated_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    preference = OffboardingPreferenceSerializer(read_only=True)
    exit_interview = ExitInterviewSerializer(read_only=True)
    clearance_items = ClearanceItemSerializer(many=True, read_only=True)
    documents = OffboardingDocumentSerializer(many=True, read_only=True)
    workflow_stages = OffboardingWorkflowStageSerializer(many=True, read_only=True)

    class Meta:
        model = OffboardingRecord
        fields = [
            "id", "employee", "employee_name", "initiated_by", "initiated_by_name",
            "resignation_date", "last_working_day", "reason",
            "status", "status_display", "remarks",
            "preference", "exit_interview", "clearance_items", "documents", "workflow_stages",
            "created_at", "updated_at",
        ]
        read_only_fields = [
            "id", "employee_name", "initiated_by", "initiated_by_name",
            "status_display", "preference", "exit_interview",
            "clearance_items", "documents", "workflow_stages",
            "created_at", "updated_at",
        ]

    def get_employee_name(self, obj):
        return _name(obj.employee)

    def get_initiated_by_name(self, obj):
        return _name(obj.initiated_by)


class OffboardingRecordListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views (no nested collections)."""
    employee_name = serializers.SerializerMethodField()
    initiated_by_name = serializers.SerializerMethodField()
    status_display = serializers.CharField(source="get_status_display", read_only=True)

    class Meta:
        model = OffboardingRecord
        fields = [
            "id", "employee", "employee_name",
            "initiated_by", "initiated_by_name",
            "resignation_date", "last_working_day",
            "reason", "remarks",
            "status", "status_display",
            "created_at", "updated_at",
        ]

    def get_employee_name(self, obj):
        return _name(obj.employee)

    def get_initiated_by_name(self, obj):
        return _name(obj.initiated_by)