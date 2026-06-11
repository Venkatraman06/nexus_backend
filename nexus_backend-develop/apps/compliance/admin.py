from django.contrib import admin
from .models import HRComplianceDocument, PolicyDocument


@admin.register(HRComplianceDocument)
class HRComplianceDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "employee", "document_type", "effective_date", "is_acknowledged", "created_at"]
    list_filter = ["document_type", "is_acknowledged"]
    search_fields = ["title", "employee__first_name", "employee__last_name", "employee__email"]
    raw_id_fields = ["employee"]


@admin.register(PolicyDocument)
class PolicyDocumentAdmin(admin.ModelAdmin):
    list_display = ["title", "version", "is_published", "effective_date", "created_at"]
    list_filter = ["is_published"]
    search_fields = ["title"]
