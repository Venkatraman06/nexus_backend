from django.contrib import admin

from .models import Conversation, ConversationParticipant, ConversationAuditLog


@admin.register(Conversation)
class ConversationAdmin(admin.ModelAdmin):
    list_display = ["id", "type", "name", "is_archived", "last_message_at"]
    list_filter = ["type", "is_archived"]
    search_fields = ["name"]


@admin.register(ConversationParticipant)
class ConversationParticipantAdmin(admin.ModelAdmin):
    list_display = ["conversation", "employee", "role", "is_favorite", "muted"]
    raw_id_fields = ["conversation", "employee"]


admin.site.register(ConversationAuditLog)
