from django.contrib import admin

from .models import FollowUp


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "priority", "assignee", "due_date", "start_time", "end_time", "workflow_state", "is_active")
    list_filter = ("type", "priority", "workflow_state", "is_active")
    search_fields = ("title", "description")
