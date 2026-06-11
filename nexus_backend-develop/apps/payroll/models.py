from decimal import Decimal

from django.conf import settings
from django.db import models

from apps.common.models import BaseModel


class PayrollStatus(models.TextChoices):
    DRAFT     = "DRAFT",     "Draft"
    FINALIZED = "FINALIZED", "Finalized"
    PAID      = "PAID",      "Paid"
    CANCELLED = "CANCELLED", "Cancelled"


class PaymentMode(models.TextChoices):
    BANK_TRANSFER = "BANK_TRANSFER", "Bank Transfer"
    CASH          = "CASH",          "Cash"
    CHEQUE        = "CHEQUE",        "Cheque"
    UPI           = "UPI",           "UPI"


MONTH_CHOICES = [
    (1,"January"),(2,"February"),(3,"March"),(4,"April"),
    (5,"May"),(6,"June"),(7,"July"),(8,"August"),
    (9,"September"),(10,"October"),(11,"November"),(12,"December"),
]


class Payroll(BaseModel):
    employee   = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="payrolls",
    )
    month      = models.PositiveSmallIntegerField(choices=MONTH_CHOICES)
    year       = models.PositiveIntegerField()

    # ── Earnings ──────────────────────────────────────────────────────────────
    basic_salary     = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    hra              = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    allowances       = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    overtime         = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Deductions ─────────────────────────────────────────────────────────────
    pf               = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           help_text="Provident Fund (auto: 12% of Basic)")
    tds              = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           help_text="TDS / Income Tax")
    other_deductions = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    advance_deduction= models.DecimalField(max_digits=12, decimal_places=2, default=0)

    # ── Attendance ─────────────────────────────────────────────────────────────
    working_days = models.PositiveSmallIntegerField(default=26)
    present_days = models.PositiveSmallIntegerField(default=0)
    leave_days   = models.PositiveSmallIntegerField(default=0)

    # ── Status & payment ───────────────────────────────────────────────────────
    status         = models.CharField(max_length=20, choices=PayrollStatus.choices, default=PayrollStatus.DRAFT)
    payment_mode   = models.CharField(max_length=20, choices=PaymentMode.choices, default=PaymentMode.BANK_TRANSFER)
    bank_name      = models.CharField(max_length=100, blank=True, default="")
    account_number = models.CharField(max_length=50, blank=True, default="")

    class Meta:
        db_table = "hrms_payroll"
        unique_together = ("employee", "month", "year")
        ordering = ["-year", "-month"]

    # ── Computed ───────────────────────────────────────────────────────────────
    @property
    def gross_total(self) -> Decimal:
        return self.basic_salary + self.hra + self.allowances + self.overtime

    @property
    def total_deductions(self) -> Decimal:
        return self.pf + self.tds + self.other_deductions + self.advance_deduction

    @property
    def net_salary(self) -> Decimal:
        return self.gross_total - self.total_deductions

    @property
    def month_name(self) -> str:
        return dict(MONTH_CHOICES).get(self.month, "")

    def save(self, *args, **kwargs):
        if not self.pk and self.pf == 0 and self.basic_salary > 0:
            self.pf = round(self.basic_salary * Decimal("0.12"), 2)
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} | {self.month_name} {self.year} | {self.status}"
