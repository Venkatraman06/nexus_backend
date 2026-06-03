from django.contrib import admin
from .models import AttendanceRecord, LeaveType, LeaveBalance, LeaveRequest

@admin.register(LeaveType)
class LeaveTypeAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "max_days", "is_paid", "is_active"]

@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = ["employee", "date", "status", "check_in", "check_out"]
    list_filter = ["status", "date"]

@admin.register(LeaveBalance)
class LeaveBalanceAdmin(admin.ModelAdmin):
    list_display = ["employee", "leave_type", "year", "total_days", "used_days"]

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ["employee", "leave_type", "start_date", "end_date", "days_count", "status"]
    list_filter = ["status", "leave_type"]
