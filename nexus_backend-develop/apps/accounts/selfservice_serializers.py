from rest_framework import serializers
from apps.common.validators import validate_phone
from .selfservice_models import EmployeeEmergencyContact, EmployeeDocument


class EmployeeEmergencyContactSerializer(serializers.ModelSerializer):
    def validate_phone(self, value: str) -> str:
        return validate_phone(value, "Emergency contact phone")

    class Meta:
        model = EmployeeEmergencyContact
        fields = ["id", "name", "phone", "relationship"]


class EmployeeDocumentSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    document_type_display = serializers.CharField(source="get_document_type_display", read_only=True)

    class Meta:
        model = EmployeeDocument
        fields = [
            "id", "document_type", "document_type_display",
            "title", "file", "file_url", "uploaded_at"
        ]
        read_only_fields = ["id", "uploaded_at", "file_url"]

    def get_file_url(self, obj):
        try:
            return obj.file.url if obj.file else None
        except Exception:
            return None
