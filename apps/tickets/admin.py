from django.contrib import admin

from .models import Ticket, TicketAttachment, TicketComment, TicketHistory


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    list_display = ["ticket_id", "title", "type", "priority", "project", "assignee", "approved"]
    list_filter = ["type", "priority", "approved"]
    search_fields = ["ticket_id", "title"]
    raw_id_fields = ["project", "assignee", "reporter", "parent"]


@admin.register(TicketComment)
class TicketCommentAdmin(admin.ModelAdmin):
    list_display = ["ticket", "author", "created_at"]
    raw_id_fields = ["ticket", "author"]


admin.site.register(TicketAttachment)
admin.site.register(TicketHistory)
