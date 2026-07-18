from django.contrib import admin

from .models import Document, DocumentLineItem


class DocumentLineItemInline(admin.TabularInline):
    model        = DocumentLineItem
    extra        = 0
    fields       = ["description", "quantity", "rate", "gst_percentage", "amount", "sort_order"]
    readonly_fields = ["amount"]


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display   = ["document_number", "document_type", "client_name", "status", "total_amount", "created_at"]
    list_filter    = ["document_type", "status", "currency"]
    search_fields  = ["document_number", "client_name", "client__name"]
    readonly_fields = ["document_number", "subtotal", "gst_amount", "total_amount", "created_at", "updated_at"]
    raw_id_fields  = ["client", "project", "division", "created_by", "updated_by"]
    inlines        = [DocumentLineItemInline]


@admin.register(DocumentLineItem)
class DocumentLineItemAdmin(admin.ModelAdmin):
    list_display   = ["document", "description", "quantity", "rate", "gst_percentage", "amount"]
    search_fields  = ["document__document_number", "description"]
    readonly_fields = ["amount"]
