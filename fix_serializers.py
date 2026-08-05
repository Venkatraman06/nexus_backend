import re

with open('apps/expenses/serializers.py', 'r') as f:
    content = f.read()

content = content.replace(
    "from .models import CompanyExpense, ExpenseStatus",
    "from .models import CompanyExpense, ExpenseStatus, ExpenseAttachment"
)

attachment_serializer = """

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
"""

content = content.replace("class ExpenseDetailSerializer(ExpenseListSerializer):", attachment_serializer.strip())
content = content.replace('"attachment", "rejection_reason", "notes",', '"attachment", "attachments", "rejection_reason", "notes",')

with open('apps/expenses/serializers.py', 'w') as f:
    f.write(content)
