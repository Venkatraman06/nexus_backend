from django.contrib import admin
from .models import Milestone, Invoice, Payment, PaymentAllocation


@admin.register(Milestone)
class MilestoneAdmin(admin.ModelAdmin):
    list_display = ["milestone_name", "project", "percentage", "amount", "due_date", "status"]
    list_filter  = ["status"]
    search_fields = ["milestone_name", "project__name"]


class PaymentAllocationInline(admin.TabularInline):
    model = PaymentAllocation
    extra = 0
    fields = ["invoice", "allocated_amount", "notes"]


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "invoice_type", "invoice_date", "client", "project", "total_amount", "is_cancelled"]
    list_filter  = ["invoice_type", "is_cancelled"]
    search_fields = ["invoice_number", "client__name"]
    inlines = [PaymentAllocationInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["payment_reference", "payment_date", "client", "project", "payment_amount", "payment_mode"]
    list_filter  = ["payment_mode"]
    search_fields = ["payment_reference", "client__name", "bank_reference"]
    inlines = [PaymentAllocationInline]


@admin.register(PaymentAllocation)
class PaymentAllocationAdmin(admin.ModelAdmin):
    list_display = ["payment", "invoice", "allocated_amount", "created_at"]
    search_fields = ["payment__payment_reference", "invoice__invoice_number"]
