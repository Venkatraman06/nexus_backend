from django.conf import settings
from django.db import models

from apps.common.models import BaseModel
from packages.storages.dynamic_storage import DynamicS3Storage


class OffboardingStatus(models.TextChoices):
    INITIATED           = "INITIATED",           "Initiated"
    PREFERENCE_PENDING  = "PREFERENCE_PENDING",   "Preference Pending"
    CLEARANCE_PENDING   = "CLEARANCE_PENDING",    "Clearance Pending"
    INTERVIEW_PENDING   = "INTERVIEW_PENDING",    "Exit Interview Pending"
    DOCUMENTS_PENDING   = "DOCUMENTS_PENDING",    "Documents Pending"
    COMPLETED           = "COMPLETED",            "Completed"
    CANCELLED           = "CANCELLED",            "Cancelled"


class OffboardingRecord(BaseModel):
    """
    Root record for one employee's offboarding process.
    Preference / Clearance / Exit Interview / Documents / Workflow all hang off this.
    """
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="offboarding_records",
    )
    initiated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="offboarding_initiated",
    )
    resignation_date = models.DateField(null=True, blank=True)
    last_working_day = models.DateField(null=True, blank=True)
    reason = models.TextField(blank=True, default="")
    status = models.CharField(
        max_length=30,
        choices=OffboardingStatus.choices,
        default=OffboardingStatus.INITIATED,
    )
    remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hrms_offboarding_record"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.employee} â€“ {self.status}"


class OffboardingPreference(BaseModel):
    """Employee's stated preferences captured at the start of offboarding."""
    offboarding = models.OneToOneField(
        OffboardingRecord,
        on_delete=models.CASCADE,
        related_name="preference",
    )
    preferred_last_working_day = models.DateField(null=True, blank=True)
    reason_for_leaving = models.TextField(blank=True, default="")
    will_serve_notice_period = models.BooleanField(default=True)
    feedback = models.TextField(blank=True, default="")
    remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hrms_offboarding_preference"

    def __str__(self):
        return f"Preference â€“ {self.offboarding.employee}"


class ClearanceItem(BaseModel):
    """Department-wise clearance checklist item (IT, Finance, Admin, HR, etc.)."""
    offboarding = models.ForeignKey(
        OffboardingRecord,
        on_delete=models.CASCADE,
        related_name="clearance_items",
    )
    department = models.CharField(max_length=100)
    item_name = models.CharField(max_length=255)
    is_cleared = models.BooleanField(default=False)
    cleared_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="clearance_items_cleared",
    )
    cleared_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hrms_offboarding_clearance_item"
        ordering = ["department", "created_at"]

    def __str__(self):
        return f"{self.department} â€“ {self.item_name}"


class ExitInterview(BaseModel):
    """Exit interview record â€” one per offboarding."""
    offboarding = models.OneToOneField(
        OffboardingRecord,
        on_delete=models.CASCADE,
        related_name="exit_interview",
    )
    interview_date = models.DateField(null=True, blank=True)
    interviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="exit_interviews_conducted",
    )
    notes = models.TextField(blank=True, default="")
    rating = models.PositiveSmallIntegerField(null=True, blank=True)  # e.g. 1-5
    would_recommend = models.BooleanField(null=True, blank=True)
    is_completed = models.BooleanField(default=False)

    class Meta:
        db_table = "hrms_offboarding_exit_interview"

    def __str__(self):
        return f"Exit Interview â€“ {self.offboarding.employee}"


class OffboardingDocumentType(models.TextChoices):
    RESIGNATION_LETTER = "RESIGNATION_LETTER", "Resignation Letter"
    RELIEVING_LETTER    = "RELIEVING_LETTER",    "Relieving Letter"
    EXPERIENCE_LETTER   = "EXPERIENCE_LETTER",   "Experience Letter"
    FNF_STATEMENT        = "FNF_STATEMENT",        "Full & Final Settlement"
    OTHER                = "OTHER",                "Other"


class OffboardingDocument(BaseModel):
    """Documents exchanged during offboarding (uploaded by HR or employee)."""
    offboarding = models.ForeignKey(
        OffboardingRecord,
        on_delete=models.CASCADE,
        related_name="documents",
    )
    document_type = models.CharField(
        max_length=30,
        choices=OffboardingDocumentType.choices,
        default=OffboardingDocumentType.OTHER,
    )
    title = models.CharField(max_length=255)
    file = models.FileField(
        upload_to="offboarding-documents/",
        storage=DynamicS3Storage,
    )
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="offboarding_documents_uploaded",
    )

    class Meta:
        db_table = "hrms_offboarding_document"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} â€“ {self.offboarding.employee}"


class WorkflowStageStatus(models.TextChoices):
    PENDING     = "PENDING",     "Pending"
    IN_PROGRESS = "IN_PROGRESS", "In Progress"
    COMPLETED   = "COMPLETED",   "Completed"
    SKIPPED     = "SKIPPED",     "Skipped"


class OffboardingWorkflowStage(BaseModel):
    """Ordered workflow stages tracked per offboarding record."""
    offboarding = models.ForeignKey(
        OffboardingRecord,
        on_delete=models.CASCADE,
        related_name="workflow_stages",
    )
    stage_name = models.CharField(max_length=100)
    order = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(
        max_length=20,
        choices=WorkflowStageStatus.choices,
        default=WorkflowStageStatus.PENDING,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="offboarding_stages_assigned",
    )
    completed_date = models.DateField(null=True, blank=True)
    remarks = models.TextField(blank=True, default="")

    class Meta:
        db_table = "hrms_offboarding_workflow_stage"
        ordering = ["offboarding", "order"]

    def __str__(self):
        return f"{self.stage_name} â€“ {self.offboarding.employee}"