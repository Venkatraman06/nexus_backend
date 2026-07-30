from rest_framework import serializers
from .models import CompanyExpense, ExpenseStatus, ExpenseAttachment


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


class ExpenseAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = ExpenseAttachment
        fields = [
            "id", "file", "original_name", "file_size", "content_type",
            "uploaded_by", "uploaded_by_name", "created_at"
        ]
        read_only_fields = ["id", "created_at", "uploaded_by", "file_size", "content_type", "original_name"]

class ExpenseDetailSerializer(ExpenseListSerializer):
    attachments = ExpenseAttachmentSerializer(many=True, read_only=True)
    class Meta(ExpenseListSerializer.Meta):
        fields = ExpenseListSerializer.Meta.fields + [
            "attachment", "attachments", "rejection_reason", "notes",
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


from .models import EmployeeReimbursement, ReimbursementAttachment, ReimbursementAuditLog, ReimbursementStatus


class ReimbursementAttachmentSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.CharField(source="uploaded_by.full_name", read_only=True)

    class Meta:
        model = ReimbursementAttachment
        fields = [
            "id", "file", "original_name", "file_size", "content_type",
            "uploaded_by", "uploaded_by_name", "created_at"
        ]
        read_only_fields = ["id", "created_at", "uploaded_by", "file_size", "content_type", "original_name"]


class ReimbursementAuditLogSerializer(serializers.ModelSerializer):
    performed_by_name = serializers.CharField(source="performed_by.full_name", read_only=True)
    from_status_label = serializers.CharField(source="get_from_status_display", read_only=True)
    to_status_label   = serializers.CharField(source="get_to_status_display",   read_only=True)

    class Meta:
        model = ReimbursementAuditLog
        fields = [
            "id", "from_status", "from_status_label", "to_status", "to_status_label",
            "performed_by", "performed_by_name", "comments", "created_at"
        ]


class EmployeeReimbursementListSerializer(serializers.ModelSerializer):
    employee_name      = serializers.CharField(source="employee.full_name",  read_only=True)
    employee_code      = serializers.CharField(source="employee.employee_code", read_only=True)
    department_name    = serializers.CharField(source="employee.department_ref.name", read_only=True, default=None)
    category_label     = serializers.CharField(source="get_category_display", read_only=True)
    status_label       = serializers.CharField(source="get_status_display",   read_only=True)
    payment_method_label = serializers.CharField(source="get_payment_method_display", read_only=True)
    project_name       = serializers.CharField(source="project.name", read_only=True, default=None)
    project_code       = serializers.CharField(source="project.code", read_only=True, default=None)
    client_name        = serializers.CharField(source="client.name", read_only=True, default=None)
    reviewed_by_name   = serializers.CharField(source="reviewed_by.full_name", read_only=True, default=None)
    paid_by_name       = serializers.CharField(source="paid_by.full_name", read_only=True, default=None)

    class Meta:
        model = EmployeeReimbursement
        fields = [
            "id", "claim_number", "employee", "employee_name", "employee_code", "department_name",
            "title", "category", "category_label", "description", "project", "project_name", "project_code",
            "client", "client_name", "expense_date", "amount_claimed", "payment_method", "payment_method_label",
            "additional_notes", "status", "status_label", "reviewed_by", "reviewed_by_name", "reviewed_at",
            "review_comments", "paid_by", "paid_by_name", "paid_at", "linked_expense", "created_at",
        ]


class EmployeeReimbursementDetailSerializer(EmployeeReimbursementListSerializer):
    attachments = ReimbursementAttachmentSerializer(many=True, read_only=True)
    audit_logs  = ReimbursementAuditLogSerializer(many=True, read_only=True)

    class Meta(EmployeeReimbursementListSerializer.Meta):
        fields = EmployeeReimbursementListSerializer.Meta.fields + [
            "attachment", "attachments", "audit_logs", "updated_at"
        ]


class EmployeeReimbursementCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmployeeReimbursement
        fields = [
            "title", "category", "description", "project", "client",
            "expense_date", "amount_claimed", "payment_method",
            "attachment", "additional_notes",
        ]

    def validate_amount_claimed(self, value):
        if value <= 0:
            raise serializers.ValidationError("Claimed amount must be positive.")
        return value

