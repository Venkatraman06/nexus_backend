import uuid
from django.db import models
from django.conf import settings
from packages.storages.dynamic_storage import DynamicS3Storage


class EmployeeEmergencyContact(models.Model):
    """
    Stores emergency contact details for an employee.
    Linked One-to-One to avoid altering the core Employee model directly.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.OneToOneField(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="emergency_contact",
    )
    name = models.CharField(max_length=150, blank=True, default="")
    phone = models.CharField(max_length=20, blank=True, default="")
    relationship = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        db_table = "hrms_employee_emergency_contact"

    def __str__(self):
        return f"Emergency Contact for {self.employee.full_name or self.employee.username}: {self.name}"


class EmployeeDocument(models.Model):
    """
    Stores official documents uploaded by the employee (Identity Card, PAN Card, Passport, Certificates).
    """
    class DocumentType(models.TextChoices):
        IDENTITY_CARD = "IDENTITY_CARD", "Identity Card"
        PAN_CARD = "PAN_CARD", "PAN Card"
        PASSPORT = "PASSPORT", "Passport"
        CERTIFICATE = "CERTIFICATE", "Certificate"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    employee = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="uploaded_documents",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.CERTIFICATE,
    )
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to="employee-documents/",
        storage=DynamicS3Storage,
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hrms_employee_document"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.employee.full_name or self.employee.username} - {self.get_document_type_display()} - {self.title}"
