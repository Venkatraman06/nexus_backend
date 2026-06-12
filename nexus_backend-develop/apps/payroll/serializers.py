from rest_framework import serializers
from .models import Payroll


class PayrollSerializer(serializers.ModelSerializer):
    employee_name  = serializers.CharField(source="employee.full_name", read_only=True)
    employee_code  = serializers.CharField(source="employee.employee_code", read_only=True)
    designation    = serializers.SerializerMethodField()
    department     = serializers.SerializerMethodField()
    month_name     = serializers.CharField(read_only=True)
    gross_total    = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    total_deductions = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)
    net_salary     = serializers.DecimalField(max_digits=12, decimal_places=2, read_only=True)

    class Meta:
        model = Payroll
        fields = [
            "id", "employee", "employee_name", "employee_code",
            "designation", "department", "month", "month_name", "year",
            # earnings
            "basic_salary", "hra", "allowances", "overtime",
            "gross_total",
            # deductions
            "pf", "tds", "other_deductions", "advance_deduction",
            "total_deductions",
            # attendance
            "working_days", "present_days", "leave_days",
            # result
            "net_salary",
            # meta
            "status", "payment_mode", "bank_name", "account_number",
            "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_designation(self, obj):
        try:
            return obj.employee.designation_ref.name if obj.employee.designation_ref_id else (obj.employee.designation or "")
        except Exception:
            return ""

    def get_department(self, obj):
        try:
            return obj.employee.department_ref.name if obj.employee.department_ref_id else (obj.employee.department or "")
        except Exception:
            return ""

    def validate(self, data):
        emp   = data.get("employee", getattr(self.instance, "employee", None))
        month = data.get("month",    getattr(self.instance, "month", None))
        year  = data.get("year",     getattr(self.instance, "year", None))
        if emp and month and year:
            qs = Payroll.objects.filter(employee=emp, month=month, year=year, is_deleted=False)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError(
                    f"Payroll for {emp.full_name} — {month}/{year} already exists."
                )
        return data
