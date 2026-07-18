from django.contrib import admin
from .models import CompanyExpense


@admin.register(CompanyExpense)
class CompanyExpenseAdmin(admin.ModelAdmin):
    list_display   = ["expense_number", "date", "category", "description", "amount", "status", "paid_by"]
    list_filter    = ["category", "status", "payment_mode"]
    search_fields  = ["expense_number", "description", "reference_number"]
    readonly_fields = ["expense_number", "created_at", "updated_at"]
