from rest_framework import serializers

from .models import HRComplianceDocument, PolicyDocument


class HRComplianceDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    employee_name = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(
        source="get_document_type_display", read_only=True
    )

    class Meta:
        model = HRComplianceDocument
        fields = [
            "id", "employee", "employee_name",
            "document_type", "document_type_display",
            "title", "description", "effective_date", "version",
            "file", "file_url",
            "is_acknowledged", "acknowledged_date",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "file_url", "employee_name", "document_type_display", "created_at", "updated_at"]

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None

    def get_employee_name(self, obj):
        return getattr(obj.employee, "full_name", None) or str(obj.employee)


class PolicyDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    uploaded_by_name = serializers.SerializerMethodField()

    class Meta:
        model = PolicyDocument
        fields = [
            "id", "title", "version", "description",
            "effective_date", "file", "file_url",
            "is_published", "is_active",
            "created_by", "uploaded_by_name",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "file_url", "uploaded_by_name", "created_by", "created_at", "updated_at"]

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None

    def get_uploaded_by_name(self, obj):
        if not obj.created_by:
            return None
        return getattr(obj.created_by, "full_name", None) or str(obj.created_by)
