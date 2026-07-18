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
