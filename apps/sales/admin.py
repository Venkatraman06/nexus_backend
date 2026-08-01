from django.contrib import admin
from .models import TrainingCategory, Deal, Quotation


@admin.register(TrainingCategory)
class TrainingCategoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "color", "created_at")
    search_fields = ("name",)


@admin.register(Deal)
class DealAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "client", "training_category", "expected_value", "stage", "created_at")
    list_filter = ("stage", "training_category")
    search_fields = ("title", "description", "client__name")


@admin.register(Quotation)
class QuotationAdmin(admin.ModelAdmin):
    list_display = ("id", "quote_no", "client", "training_cost", "gst", "net_amount", "status", "sent_at")
    list_filter = ("status",)
    search_fields = ("quote_no", "client__name")
