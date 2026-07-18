from django.contrib import admin
from .models import Payroll

@admin.register(Payroll)
class PayrollAdmin(admin.ModelAdmin):
    list_display = ["employee", "month", "year", "net_salary", "status", "payment_mode"]
    list_filter  = ["status", "year", "month"]
    search_fields= ["employee__first_name", "employee__last_name"]
