from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Employee, EmployeeCertificate


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = ["username", "full_name", "email", "designation", "department", "is_pmo", "is_manager", "status", "is_active"]
    list_filter = ["status", "is_pmo", "is_manager", "is_staff", "department"]
    search_fields = ["username", "email", "first_name", "last_name", "employee_code"]
    ordering = ["first_name", "last_name"]
    # readonly_fields = ["keycloak_id", "last_login"]
    readonly_fields = ["last_login"]

    filter_horizontal = ("groups", "user_permissions")
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Personal", {"fields": ("first_name", "last_name", "email", "phone_number", "bio", "profile_picture")}),
        ("Employment", {"fields": ("employee_code", "designation", "department", "joining_date", "status")}),
        ("Roles", {"fields": ("is_pmo", "is_manager", "is_staff", "is_active", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Keycloak", {"fields": ("keycloak_id",)}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("username", "email", "password1", "password2"),
        }),
    )


@admin.register(EmployeeCertificate)
class EmployeeCertificateAdmin(admin.ModelAdmin):
    list_display = ["employee", "title", "issuing_organization", "issue_date", "expiry_date"]
    list_filter = ["issuing_organization"]
    search_fields = ["employee__username", "title"]
    raw_id_fields = ["employee"]
