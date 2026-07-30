import re

with open('apps/expenses/views.py', 'r') as f:
    content = f.read()

content = content.replace(
    "from .models import CompanyExpense, ExpenseStatus",
    "from .models import CompanyExpense, ExpenseStatus, ExpenseAttachment"
)

content = content.replace(
    "ExpenseListSerializer, ExpenseDetailSerializer, ExpenseCreateSerializer,",
    "ExpenseListSerializer, ExpenseDetailSerializer, ExpenseCreateSerializer, ExpenseAttachmentSerializer,"
)

extra_views = """    @action(detail=True, methods=["post"], url_path="attachments")
    def upload_attachment(self, request, pk=None):
        expense = self.get_object()
        file_obj = request.FILES.get("file")
        if not file_obj:
            return Response({"detail": "No file provided."}, status=status.HTTP_400_BAD_REQUEST)
        
        attachment = ExpenseAttachment.objects.create(
            expense=expense,
            file=file_obj,
            original_name=file_obj.name,
            file_size=file_obj.size,
            content_type=file_obj.content_type,
            uploaded_by=request.user
        )
        return Response(ExpenseAttachmentSerializer(attachment).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["delete"], url_path=r"attachments/(?P<attachment_id>[^/.]+)")
    def delete_attachment(self, request, pk=None, attachment_id=None):
        expense = self.get_object()
        try:
            attachment = expense.attachments.get(id=attachment_id)
            attachment.delete()
            return Response(status=status.HTTP_204_NO_CONTENT)
        except ExpenseAttachment.DoesNotExist:
            return Response({"detail": "Attachment not found."}, status=status.HTTP_404_NOT_FOUND)

    @action(detail=False, methods=["get"], url_path="summary")"""

content = content.replace('    @action(detail=False, methods=["get"], url_path="summary")', extra_views)

with open('apps/expenses/views.py', 'w') as f:
    f.write(content)
