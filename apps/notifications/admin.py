from django.contrib import admin

from apps.notifications.models import Notification, NotificationEventLog, NotificationTemplate


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = ("event_type", "severity", "is_active")
    search_fields = ("event_type", "title_template")


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("title", "recipient", "event_type", "severity", "is_read", "created_at")
    list_filter = ("event_type", "severity", "is_read", "channel")
    search_fields = ("title", "recipient__email", "recipient__username")
    readonly_fields = ("created_at", "read_at")


@admin.register(NotificationEventLog)
class NotificationEventLogAdmin(admin.ModelAdmin):
    list_display = ("event_type", "reference_type", "reference_id", "notifications_created", "created_at")
    list_filter = ("event_type",)
    readonly_fields = ("created_at", "processed_at")
