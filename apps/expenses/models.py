import datetime
from django.db import models
from apps.common.models import BaseModel


class ExpenseCategory(models.TextChoices):
    TRAVEL       = "TRAVEL",       "Travel & Transport"
    MEALS        = "MEALS",        "Meals & Entertainment"
    OFFICE       = "OFFICE",       "Office Supplies"
    SOFTWARE     = "SOFTWARE",     "Software & Subscriptions"
    MARKETING    = "MARKETING",    "Marketing & Advertising"
    UTILITIES    = "UTILITIES",    "Utilities & Internet"
    EQUIPMENT    = "EQUIPMENT",    "Equipment & Hardware"
    RENT         = "RENT",         "Rent & Facilities"
    OTHER        = "OTHER",        "Other"


class ExpenseStatus(models.TextChoices):
    DRAFT       = "DRAFT",       "Draft"
    SUBMITTED   = "SUBMITTED",   "Submitted"
    APPROVED    = "APPROVED",    "Approved"
    REJECTED    = "REJECTED",    "Rejected"
    REIMBURSED  = "REIMBURSED",  "Reimbursed"


class ExpensePaymentMode(models.TextChoices):
    CASH            = "CASH",           "Cash"
    CORPORATE_CARD  = "CORPORATE_CARD", "Corporate Card"
    PERSONAL_CARD   = "PERSONAL_CARD",  "Personal Card"
    UPI             = "UPI",            "UPI"
    BANK_TRANSFER   = "BANK_TRANSFER",  "Bank Transfer"
    CHEQUE          = "CHEQUE",         "Cheque"


class CompanyExpense(BaseModel):
    expense_number    = models.CharField(max_length=50, unique=True, blank=True)
    date              = models.DateField()
    category          = models.CharField(
        max_length=20, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER
    )
    description       = models.CharField(max_length=500)
    amount            = models.DecimalField(max_digits=12, decimal_places=2)
    paid_by           = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.PROTECT,
        related_name="expenses",
    )
    project           = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="expenses",
    )
    client            = models.ForeignKey(
        "projects.Client",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="expenses",
    )
    payment_mode      = models.CharField(
        max_length=20, choices=ExpensePaymentMode.choices, default=ExpensePaymentMode.CASH
    )
    reference_number  = models.CharField(max_length=100, blank=True, default="",
                                         help_text="Bill / receipt / invoice number")
    attachment        = models.FileField(upload_to="expenses/receipts/", null=True, blank=True)
    status            = models.CharField(
        max_length=20, choices=ExpenseStatus.choices, default=ExpenseStatus.DRAFT
    )
    approved_by       = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="approved_expenses",
    )
    approved_at       = models.DateTimeField(null=True, blank=True)
    rejection_reason  = models.TextField(blank=True, default="")
    notes             = models.TextField(blank=True, default="")

    class Meta:
        db_table = "crm_expense"
        ordering = ["-date", "-created_at"]

    def __str__(self):
        return f"{self.expense_number} — {self.description[:50]}"

    @classmethod
    def generate_number(cls) -> str:
        yy = datetime.date.today().strftime("%y")
        prefix = f"EXP-{yy}"
        count = cls.objects.filter(expense_number__startswith=prefix).count() + 1
        num = f"{prefix}{count:04d}"
        while cls.objects.filter(expense_number=num).exists():
            count += 1
            num = f"{prefix}{count:04d}"
        return num

    def save(self, *args, **kwargs):
        if not self.expense_number:
            self.expense_number = self.generate_number()
        super().save(*args, **kwargs)

class ExpenseAttachment(BaseModel):
    expense = models.ForeignKey(CompanyExpense, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="expenses/attachments/")
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey("accounts.Employee", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "crm_expense_attachment"
        ordering = ["-created_at"]


class ReimbursementStatus(models.TextChoices):
    DRAFT            = "DRAFT",            "Draft"
    SUBMITTED        = "SUBMITTED",        "Submitted"
    UNDER_HR_REVIEW  = "UNDER_HR_REVIEW",  "Under HR Review"
    INFO_REQUESTED   = "INFO_REQUESTED",   "Info Requested"
    APPROVED         = "APPROVED",         "Approved"
    REJECTED         = "REJECTED",         "Rejected"
    PAID             = "PAID",             "Paid"


class EmployeeReimbursement(BaseModel):
    claim_number      = models.CharField(max_length=50, unique=True, blank=True)
    employee          = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.CASCADE,
        related_name="reimbursements",
    )
    title             = models.CharField(max_length=200, help_text="Expense Title")
    category          = models.CharField(
        max_length=30, choices=ExpenseCategory.choices, default=ExpenseCategory.OTHER
    )
    description       = models.TextField(help_text="Purpose or work description of expense")
    project           = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reimbursements",
    )
    client            = models.ForeignKey(
        "projects.Client",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reimbursements",
    )
    expense_date      = models.DateField()
    amount_claimed    = models.DecimalField(max_digits=12, decimal_places=2)
    payment_method    = models.CharField(
        max_length=30, choices=ExpensePaymentMode.choices, default=ExpensePaymentMode.PERSONAL_CARD
    )
    attachment        = models.FileField(upload_to="reimbursements/receipts/", null=True, blank=True)
    additional_notes  = models.TextField(blank=True, default="")
    status            = models.CharField(
        max_length=30, choices=ReimbursementStatus.choices, default=ReimbursementStatus.DRAFT
    )
    
    # Reviewer tracking
    reviewed_by       = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="reviewed_reimbursements",
    )
    reviewed_at       = models.DateTimeField(null=True, blank=True)
    review_comments   = models.TextField(blank=True, default="")

    paid_by           = models.ForeignKey(
        "accounts.Employee",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="paid_reimbursements",
    )
    paid_at           = models.DateTimeField(null=True, blank=True)

    # Linked Company Expense record automatically created on approval
    linked_expense    = models.ForeignKey(
        CompanyExpense,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="source_reimbursement",
    )

    class Meta:
        db_table = "hrms_employee_reimbursement"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.claim_number} — {self.title} ({self.employee.full_name})"

    @classmethod
    def generate_claim_number(cls) -> str:
        yy = datetime.date.today().strftime("%y")
        prefix = f"CLM-{yy}"
        count = cls.objects.filter(claim_number__startswith=prefix).count() + 1
        num = f"{prefix}{count:04d}"
        while cls.objects.filter(claim_number=num).exists():
            count += 1
            num = f"{prefix}{count:04d}"
        return num

    def save(self, *args, **kwargs):
        if not self.claim_number:
            self.claim_number = self.generate_claim_number()
        super().save(*args, **kwargs)


class ReimbursementAttachment(BaseModel):
    reimbursement = models.ForeignKey(EmployeeReimbursement, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="reimbursements/attachments/")
    original_name = models.CharField(max_length=255)
    file_size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    uploaded_by = models.ForeignKey("accounts.Employee", on_delete=models.SET_NULL, null=True, blank=True)

    class Meta:
        db_table = "hrms_reimbursement_attachment"
        ordering = ["-created_at"]


class ReimbursementAuditLog(models.Model):
    id = models.BigAutoField(primary_key=True)
    reimbursement = models.ForeignKey(EmployeeReimbursement, on_delete=models.CASCADE, related_name="audit_logs")
    from_status = models.CharField(max_length=30, choices=ReimbursementStatus.choices)
    to_status = models.CharField(max_length=30, choices=ReimbursementStatus.choices)
    performed_by = models.ForeignKey("accounts.Employee", on_delete=models.SET_NULL, null=True, blank=True)
    comments = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "hrms_reimbursement_audit_log"
        ordering = ["created_at"]

