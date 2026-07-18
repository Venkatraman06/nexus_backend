from django.contrib import admin
from .models import Allocation


@admin.register(Allocation)
class AllocationAdmin(admin.ModelAdmin):
    list_display = ["employee", "project", "allocation_percentage", "daily_hours", "start_date", "end_date", "is_active"]
    list_filter = ["is_active"]
    search_fields = ["employee__username", "project__name"]
    raw_id_fields = ["employee", "project", "created_by", "updated_by"]
    readonly_fields = ["created_at", "updated_at"]
