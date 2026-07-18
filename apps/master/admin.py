from django.contrib import admin
from .models import Holiday, LeaveType


@admin.register(Holiday)
class HolidayAdmin(admin.ModelAdmin):
    list_display = ["name", "date", "holiday_type", "is_active"]
    list_filter = ["holiday_type", "year"]


@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "max_days", "is_paid", "is_active"]
