from django.contrib import admin
from .models import WorkLog


@admin.register(WorkLog)
class WorkLogAdmin(admin.ModelAdmin):
    list_display = ["employee", "ticket", "log_date", "hours", "is_billable"]
    list_filter = ["is_billable", "log_date"]
    search_fields = ["employee__username", "ticket__ticket_id"]
    raw_id_fields = ["employee", "ticket", "created_by", "updated_by"]
    date_hierarchy = "log_date"
