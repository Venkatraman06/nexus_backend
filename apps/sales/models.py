from decimal import Decimal, ROUND_HALF_UP
from django.db import models
from django.utils import timezone
from apps.common.models import BaseModel


class TrainingCategory(BaseModel):
    name = models.CharField(max_length=120)
    color = models.CharField(max_length=20, default="#2563EB")

    class Meta:
        db_table = "sales_training_category"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Deal(BaseModel):
    STAGE_CHOICES = [
        ("Active", "Active"),
        ("Negotiation", "Negotiation"),
        ("Won", "Won"),
        ("Lost", "Lost"),
    ]

    title = models.CharField(max_length=200)
    client = models.ForeignKey("leads.Client", null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    training_category = models.ForeignKey(TrainingCategory, null=True, blank=True, on_delete=models.SET_NULL, related_name="deals")
    description = models.TextField(blank=True, default="")
    expected_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    stage = models.CharField(max_length=20, choices=STAGE_CHOICES, default="Active")
    followup_notes = models.TextField(blank=True, default="")
    last_contact = models.DateTimeField(null=True, blank=True)
    training_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "sales_deal"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} ({self.stage})"


class Quotation(BaseModel):
    STATUS_CHOICES = [
        ("PENDING", "Pending"),
        ("SENT", "Sent"),
        ("APPROVED", "Approved"),
        ("REJECTED", "Rejected"),
    ]

    quote_no = models.CharField(max_length=30, unique=True, editable=False, blank=True)
    client = models.ForeignKey("leads.Client", on_delete=models.CASCADE, related_name="sales_quotations")
    training_cost = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    gst = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    net_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="PENDING")
    sent_at = models.DateTimeField(null=True, blank=True)
    viewed_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "sales_quotation"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.quote_no or 'Draft'} - {self.client.name if self.client else 'No Client'}"

    def save(self, *args, **kwargs):
        # Auto-compute GST (18%) and Net Amount server-side
        if self.training_cost:
            cost = Decimal(str(self.training_cost))
            gst_val = (cost * Decimal("0.18")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            self.gst = gst_val
            self.net_amount = cost + gst_val

        super().save(*args, **kwargs)

        if not self.quote_no:
            seq = Quotation.objects.count() + 1000
            self.quote_no = f"Q-{seq}"
            super().save(update_fields=["quote_no"])
