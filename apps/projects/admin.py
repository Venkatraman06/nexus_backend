from django.contrib import admin
from .models import Client, Project, ProjectHistory


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "contact_email", "is_active"]
    search_fields = ["name", "code", "contact_email"]


@admin.register(Project)
class ProjectAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "client", "manager", "is_active", "business_type", "billing_type", "start_date", "end_date"]
    list_filter = ["is_active", "business_type", "billing_type"]
    search_fields = ["name", "code"]
    raw_id_fields = ["client", "manager", "created_by", "updated_by"]
    readonly_fields = ["created_at", "updated_at"]


admin.site.register(ProjectHistory)
