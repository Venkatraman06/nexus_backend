from rest_framework import serializers
from .models import CompanyExpense, ExpenseStatus


class ExpenseListSerializer(serializers.ModelSerializer):
    paid_by_name      = serializers.SerializerMethodField()
    approved_by_name  = serializers.SerializerMethodField()
    project_name      = serializers.CharField(source="project.name",  read_only=True)
    project_code      = serializers.CharField(source="project.code",  read_only=True)
    client_name       = serializers.CharField(source="client.name",   read_only=True)
    category_label    = serializers.CharField(source="get_category_display",     read_only=True)
    status_label      = serializers.CharField(source="get_status_display",       read_only=True)
    payment_mode_label = serializers.CharField(source="get_payment_mode_display", read_only=True)

    class Meta:
        model = CompanyExpense
        fields = [
            "id", "expense_number", "date", "category", "category_label",
            "description", "amount",
            "paid_by", "paid_by_name",
            "project", "project_name", "project_code",
            "client",  "client_name",
            "payment_mode", "payment_mode_label",
            "reference_number",
            "status", "status_label",
            "approved_by", "approved_by_name", "approved_at",
            "created_at",
        ]

    def get_paid_by_name(self, obj):
        try:
            return obj.paid_by.full_name
        except Exception:
            return ""

    def get_approved_by_name(self, obj):
        try:
            return obj.approved_by.full_name if obj.approved_by else None
        except Exception:
            return None


class ExpenseDetailSerializer(ExpenseListSerializer):
    class Meta(ExpenseListSerializer.Meta):
        fields = ExpenseListSerializer.Meta.fields + [
            "attachment", "rejection_reason", "notes",
            "is_active", "updated_at",
        ]
        read_only_fields = ["id", "expense_number", "created_at", "updated_at"]


class ExpenseCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = CompanyExpense
        fields = [
            "date", "category", "description", "amount",
            "paid_by", "project", "client",
            "payment_mode", "reference_number",
            "attachment", "notes",
        ]

    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError("Amount must be positive.")
        return value
