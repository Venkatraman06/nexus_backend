from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from packages.storages.dynamic_storage import DynamicS3Storage


class DocumentType(models.TextChoices):
    NDA         = "NDA",         "Non-Disclosure Agreement"
    UNDERTAKING = "UNDERTAKING", "Undertaking"
    OFFER       = "OFFER",       "Offer Letter"
    POLICY      = "POLICY",      "Internal Policy"
    OTHER       = "OTHER",       "Other"


class HRComplianceDocument(BaseModel):
    """
    Per-employee compliance documents uploaded by HR (NDA, Undertaking, etc.).
    Employees can download and sign the hard copy.
    """
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="compliance_documents",
    )
    document_type = models.CharField(
        max_length=20,
        choices=DocumentType.choices,
        default=DocumentType.OTHER,
    )
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True, default="")
    effective_date = models.DateField(null=True, blank=True)
    version = models.CharField(max_length=50, blank=True, default="")
    file = models.FileField(
        upload_to="hr-compliance/",
        storage=DynamicS3Storage,
    )
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "hrms_compliance_document"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} – {self.title}"


class PolicyDocument(BaseModel):
    """
    Company-wide policy documents. All employees can view and download.
    Only HR can upload and manage.
    """
    title = models.CharField(max_length=255)
    version = models.CharField(max_length=50, blank=True, default="")
    description = models.TextField(blank=True, default="")
    effective_date = models.DateField(null=True, blank=True)
    file = models.FileField(
        upload_to="policy-documents/",
        storage=DynamicS3Storage,
    )
    is_published = models.BooleanField(default=True)

    class Meta:
        db_table = "policy_document"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} v{self.version}"
