import datetime
from decimal import Decimal

from django.db import models
from django.utils import timezone

from apps.common.models import BaseModel


# ─────────────────────────────────────────────────────────────────────────────
# Choice enums
# ─────────────────────────────────────────────────────────────────────────────

class InvoiceType(models.TextChoices):
    ADVANCE   = "ADVANCE",   "Advance Invoice"
    MILESTONE = "MILESTONE", "Milestone Invoice"
    FINAL     = "FINAL",     "Final Invoice"
    PROFORMA  = "PROFORMA",  "Proforma Invoice"
    REGULAR   = "REGULAR",   "Regular Invoice"


class InvoiceStatus(models.TextChoices):
    UNPAID    = "UNPAID",    "Unpaid"
    PARTIAL   = "PARTIAL",   "Partial"
    PAID      = "PAID",      "Paid"
    OVERDUE   = "OVERDUE",   "Overdue"
    CANCELLED = "CANCELLED", "Cancelled"


class MilestoneStatus(models.TextChoices):
    PENDING  = "PENDING",  "Pending"
    INVOICED = "INVOICED", "Invoiced"
    PAID     = "PAID",     "Paid"


class PaymentMode(models.TextChoices):
    BANK_TRANSFER   = "BANK_TRANSFER",   "Bank Transfer"
    UPI             = "UPI",             "UPI"
    CHEQUE          = "CHEQUE",          "Cheque"
    CASH            = "CASH",            "Cash"
    ONLINE_GATEWAY  = "ONLINE_GATEWAY",  "Online Gateway"
    NEFT            = "NEFT",            "NEFT"
    RTGS            = "RTGS",            "RTGS"


# ─────────────────────────────────────────────────────────────────────────────
# Milestone
# ─────────────────────────────────────────────────────────────────────────────

class Milestone(BaseModel):
    project        = models.ForeignKey(
        "projects.Project",
        on_delete=models.CASCADE,
        related_name="billing_milestones",
    )
    milestone_name = models.CharField(max_length=200)
    description    = models.TextField(blank=True, default="")
    percentage     = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Percentage of contract value"
    )
    amount         = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    due_date       = models.DateField(null=True, blank=True)
    sequence       = models.PositiveIntegerField(default=0)
    status         = models.CharField(
        max_length=20, choices=MilestoneStatus.choices, default=MilestoneStatus.PENDING
    )

    class Meta:
        db_table = "payment_milestone"
        ordering = ["sequence", "due_date"]

    def __str__(self):
        return f"{self.project.code} — {self.milestone_name}"


# ─────────────────────────────────────────────────────────────────────────────
# Invoice
# ─────────────────────────────────────────────────────────────────────────────

class Invoice(BaseModel):
    invoice_number  = models.CharField(max_length=50, unique=True, blank=True)
    invoice_type    = models.CharField(
        max_length=20, choices=InvoiceType.choices, default=InvoiceType.REGULAR
    )
    invoice_date    = models.DateField()
    client          = models.ForeignKey(
        "projects.Client",
        on_delete=models.PROTECT,
        related_name="invoices",
    )
    project         = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="invoices",
    )
    milestone       = models.ForeignKey(
        Milestone,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="invoices",
    )
    invoice_amount  = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="Pre-tax amount"
    )
    tax_percentage  = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("18.00"),
        help_text="GST/Tax percentage"
    )
    tax_amount      = models.DecimalField(max_digits=15, decimal_places=2, default=0)
    total_amount    = models.DecimalField(
        max_digits=15, decimal_places=2,
        help_text="invoice_amount + tax_amount"
    )
    due_date        = models.DateField(null=True, blank=True)
    notes           = models.TextField(blank=True, default="")
    attachment      = models.FileField(upload_to="payment/invoices/", null=True, blank=True)
    is_cancelled    = models.BooleanField(default=False)

    class Meta:
        db_table = "payment_invoice"
        ordering = ["-invoice_date", "-created_at"]

    def __str__(self):
        return f"{self.invoice_number} — {self.client.name}"

    @classmethod
    def generate_number(cls) -> str:
        yy = datetime.date.today().strftime("%y")
        prefix = f"INV-{yy}"
        count = cls.objects.filter(invoice_number__startswith=prefix).count() + 1
        num = f"{prefix}{count:04d}"
        while cls.objects.filter(invoice_number=num).exists():
            count += 1
            num = f"{prefix}{count:04d}"
        return num

    def save(self, *args, **kwargs):
        if not self.invoice_number:
            self.invoice_number = self.generate_number()
        # Auto-compute tax and total
        self.tax_amount = (self.invoice_amount * self.tax_percentage / 100).quantize(
            Decimal("0.01")
        )
        self.total_amount = self.invoice_amount + self.tax_amount
        super().save(*args, **kwargs)

    # ── Computed receivable fields ────────────────────────────────────────

    @property
    def received_amount(self) -> Decimal:
        result = self.allocations.filter(
            payment__is_deleted=False
        ).aggregate(total=models.Sum("allocated_amount"))["total"]
        return result or Decimal("0")

    @property
    def pending_amount(self) -> Decimal:
        return self.total_amount - self.received_amount

    @property
    def status(self) -> str:
        if self.is_cancelled:
            return InvoiceStatus.CANCELLED
        received = self.received_amount
        if received >= self.total_amount:
            return InvoiceStatus.PAID
        if received > 0:
            return InvoiceStatus.PARTIAL
        today = datetime.date.today()
        if self.due_date and self.due_date < today:
            return InvoiceStatus.OVERDUE
        return InvoiceStatus.UNPAID

    @property
    def days_overdue(self) -> int:
        if self.due_date and self.pending_amount > 0:
            delta = (datetime.date.today() - self.due_date).days
            return max(0, delta)
        return 0


# ─────────────────────────────────────────────────────────────────────────────
# Payment
# ─────────────────────────────────────────────────────────────────────────────

class Payment(BaseModel):
    payment_reference = models.CharField(max_length=50, unique=True, blank=True)
    client            = models.ForeignKey(
        "projects.Client",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    project           = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="payments",
    )
    payment_date      = models.DateField()
    payment_amount    = models.DecimalField(max_digits=15, decimal_places=2)
    payment_mode      = models.CharField(
        max_length=20, choices=PaymentMode.choices, default=PaymentMode.BANK_TRANSFER
    )
    bank_reference    = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Cheque number / UTR / UPI ref / transaction ID"
    )
    remarks           = models.TextField(blank=True, default="")
    attachment        = models.FileField(upload_to="payment/receipts/", null=True, blank=True)

    class Meta:
        db_table = "payment_payment"
        ordering = ["-payment_date", "-created_at"]

    def __str__(self):
        return f"{self.payment_reference} — ₹{self.payment_amount}"

    @classmethod
    def generate_reference(cls) -> str:
        yy = datetime.date.today().strftime("%y")
        prefix = f"PAY-{yy}"
        count = cls.objects.filter(payment_reference__startswith=prefix).count() + 1
        ref = f"{prefix}{count:04d}"
        while cls.objects.filter(payment_reference=ref).exists():
            count += 1
            ref = f"{prefix}{count:04d}"
        return ref

    def save(self, *args, **kwargs):
        if not self.payment_reference:
            self.payment_reference = self.generate_reference()
        super().save(*args, **kwargs)

    @property
    def allocated_amount(self) -> Decimal:
        result = self.allocations.aggregate(total=models.Sum("allocated_amount"))["total"]
        return result or Decimal("0")

    @property
    def unallocated_amount(self) -> Decimal:
        return self.payment_amount - self.allocated_amount


# ─────────────────────────────────────────────────────────────────────────────
# PaymentAllocation — links a payment to one or more invoices
# ─────────────────────────────────────────────────────────────────────────────

class PaymentAllocation(BaseModel):
    payment          = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    invoice          = models.ForeignKey(
        Invoice,
        on_delete=models.CASCADE,
        related_name="allocations",
    )
    allocated_amount = models.DecimalField(max_digits=15, decimal_places=2)
    notes            = models.TextField(blank=True, default="")

    class Meta:
        db_table = "payment_allocation"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.payment.payment_reference} → {self.invoice.invoice_number} ₹{self.allocated_amount}"
