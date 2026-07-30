from apps.expenses.models import CompanyExpense, ExpenseAttachment
from apps.accounts.models import Employee
from django.core.files.uploadedfile import SimpleUploadedFile

try:
    expense = CompanyExpense.objects.first()
    user = Employee.objects.first()
    
    file_obj = SimpleUploadedFile("test.txt", b"file_content", content_type="text/plain")
    
    attachment = ExpenseAttachment.objects.create(
        expense=expense,
        file=file_obj,
        original_name="test.txt",
        file_size=12,
        content_type="text/plain",
        uploaded_by=user
    )
    print("Success:", attachment.id)
except Exception as e:
    import traceback
    traceback.print_exc()
