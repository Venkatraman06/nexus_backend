from decimal import Decimal, ROUND_HALF_UP

from django.db import models, transaction
from django.utils import timezone

from apps.common.models import BaseModel


TYPE_PREFIXES = {
    "quotation":        "QT",
    "proforma_invoice": "PI",
    "gst_invoice":      "GI",
    "purchase_order":   "PO",
    "receipt":          "RC",
}

QUOTATION_STATUSES = {"draft", "sent", "accepted", "rejected", "expired"}
INVOICE_STATUSES   = {"draft", "generated", "sent", "paid", "partially_paid", "overdue", "cancelled"}
PO_STATUSES        = {"draft", "sent", "accepted", "rejected", "expired"}
RECEIPT_STATUSES   = {"draft", "generated", "sent"}

ALLOWED_STATUSES_BY_TYPE = {
    "quotation":        QUOTATION_STATUSES,
    "proforma_invoice": INVOICE_STATUSES,
    "gst_invoice":      INVOICE_STATUSES,
    "purchase_order":   PO_STATUSES,
    "receipt":          RECEIPT_STATUSES,
}


class Document(BaseModel):
    DOCUMENT_TYPE_CHOICES = [
        ("quotation",        "Quotation"),
        ("proforma_invoice", "Proforma Invoice"),
        ("gst_invoice",      "GST Invoice"),
        ("purchase_order",   "Purchase Order"),
        ("receipt",          "Receipt"),
    ]

    STATUS_CHOICES = [
        ("draft",          "Draft"),
        ("sent",           "Sent"),
        ("accepted",       "Accepted"),
        ("rejected",       "Rejected"),
        ("expired",        "Expired"),
        ("generated",      "Generated"),
        ("paid",           "Paid"),
        ("partially_paid", "Partially Paid"),
        ("overdue",        "Overdue"),
        ("cancelled",      "Cancelled"),
    ]

    GST_RATE_CHOICES = [
        ("0",  "0%"),
        ("5",  "5%"),
        ("12", "12%"),
        ("18", "18%"),
        ("28", "28%"),
    ]

    document_number = models.CharField(max_length=50, unique=True, blank=True, db_index=True)
    document_type   = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, db_index=True)

    client = models.ForeignKey(
        "projects.Client",
        on_delete=models.PROTECT,
        related_name="finance_documents",
    )
    project = models.ForeignKey(
        "projects.Project",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="finance_documents",
    )
    division = models.ForeignKey(
        "master.Location",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="finance_documents",
    )

    currency    = models.CharField(max_length=3, default="INR")
    status      = models.CharField(max_length=20, choices=STATUS_CHOICES, default="draft", db_index=True)
    valid_until = models.DateField(null=True, blank=True)
    notes       = models.TextField(blank=True, default="")

    # Stored totals (recalculated on line-item changes)
    subtotal     = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gst_amount   = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    total_amount = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))

    # Client snapshot — captured at creation so the document is immutable if client changes
    client_name       = models.CharField(max_length=200, blank=True, default="")
    client_email      = models.EmailField(blank=True, default="")
    client_gst_number = models.CharField(max_length=15, blank=True, default="")
    billing_address   = models.TextField(blank=True, default="")
    shipping_address  = models.TextField(blank=True, default="")

    class Meta:
        db_table = "finance_document"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.document_number} – {self.client_name}"

    @classmethod
    def generate_document_number(cls, document_type: str) -> str:
        prefix = TYPE_PREFIXES.get(document_type, "DOC")
        year   = timezone.now().year
        with transaction.atomic():
            last = (
                cls.objects
                .select_for_update()
                .filter(document_type=document_type, document_number__startswith=f"{prefix}-{year}-")
                .order_by("-document_number")
                .first()
            )
            seq = 1
            if last and last.document_number:
                try:
                    seq = int(last.document_number.split("-")[-1]) + 1
                except (ValueError, IndexError):
                    seq = 1
            return f"{prefix}-{year}-{seq:04d}"

    def recalculate_totals(self):
        items    = self.line_items.filter(is_deleted=False)
        subtotal = Decimal("0.00")
        gst      = Decimal("0.00")
        for item in items:
            subtotal += item.amount
            gst      += (item.amount * item.gst_percentage / Decimal("100")).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
        self.subtotal     = subtotal
        self.gst_amount   = gst
        self.total_amount = subtotal + gst
        self.save(update_fields=["subtotal", "gst_amount", "total_amount", "updated_at"])


class DocumentLineItem(BaseModel):
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name="line_items",
    )
    description    = models.CharField(max_length=500)
    quantity       = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("1.00"))
    rate           = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    gst_percentage = models.DecimalField(max_digits=5,  decimal_places=2, default=Decimal("0.00"))
    amount         = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal("0.00"))
    sort_order     = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "finance_document_line_item"
        ordering = ["sort_order", "created_at"]

    def __str__(self):
        return f"{self.document.document_number} | {self.description}"

    def save(self, *args, **kwargs):
        # Recalculate amount unless we're doing a targeted field-only update
        if not kwargs.get("update_fields"):
            self.amount = (self.quantity * self.rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        super().save(*args, **kwargs)
