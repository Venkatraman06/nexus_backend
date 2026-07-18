from django.contrib import admin

from .models import FollowUp


@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ("title", "type", "priority", "get_assignees", "start_date", "end_date", "start_time", "end_time", "workflow_state", "is_active")
    list_filter = ("type", "priority", "workflow_state", "is_active")
    search_fields = ("title", "description")

    def get_assignees(self, obj):
        return ", ".join(a.full_name for a in obj.assignees.all())
    get_assignees.short_description = "Assignees"
