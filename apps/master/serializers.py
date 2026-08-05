from rest_framework import serializers
from .models import (
    Designation, Department, Location, Grade, EmploymentType,
    ShiftCategory, RateCard, ClientCategory, BusinessType, BillingType,
    FollowupTypeMaster,
)


class DropdownSerializer(serializers.ModelSerializer):
    """Minimal id/name/slug for all dropdown lists."""
    class Meta:
        fields = ["id", "name", "slug"]


class DesignationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Designation
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class DesignationDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = Designation


class DepartmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class DepartmentDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = Department


class LocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "slug", "city", "state", "country", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class LocationDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Location
        fields = ["id", "name", "slug", "city", "state"]


class GradeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Grade
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class GradeDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = Grade


class EmploymentTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmploymentType
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class EmploymentTypeDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = EmploymentType

class ShiftCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftCategory
        fields = ["id", "name", "slug", "start_time", "end_time", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]

    def validate(self, data):
        start = data.get("start_time") or (self.instance.start_time if self.instance else None)
        end   = data.get("end_time")   or (self.instance.end_time   if self.instance else None)
        if start and end:
            import datetime
            s = datetime.datetime.combine(datetime.date.today(), start)
            e = datetime.datetime.combine(datetime.date.today(), end)
            if e <= s:
                e += datetime.timedelta(days=1)
            diff_hours = (e - s).seconds / 3600
            if abs(diff_hours - 9) > 0.01:
                raise serializers.ValidationError("Shift duration must be exactly 9 hours.")
        return data


class ShiftCategoryDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShiftCategory
        fields = ["id", "name", "start_time", "end_time"]


class ClientCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientCategory
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class ClientCategoryDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = ClientCategory


class BusinessTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessType
        fields = ["id", "name", "slug", "prefix", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class BusinessTypeDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = BusinessType
        fields = ["id", "name", "slug", "prefix"]


class BillingTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = BillingType
        fields = ["id", "name", "slug", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class BillingTypeDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = BillingType


class FollowupTypeMasterSerializer(serializers.ModelSerializer):
    class Meta:
        model = FollowupTypeMaster
        fields = ["id", "name", "slug", "color", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class FollowupTypeDropdownSerializer(DropdownSerializer):
    class Meta(DropdownSerializer.Meta):
        model = FollowupTypeMaster


class RateCardSerializer(serializers.ModelSerializer):
    designation_name    = serializers.CharField(source="designation_ref.name", read_only=True)
    department_name     = serializers.CharField(source="department_ref.name",  read_only=True)
    monthly_hr_cost     = serializers.SerializerMethodField()
    monthly_client_rate = serializers.SerializerMethodField()

    class Meta:
        model  = RateCard
        fields = [
            "id", "designation_ref", "designation_name",
            "department_ref", "department_name",
            "hr_daily_rate", "client_billing_rate",
            "monthly_hr_cost", "monthly_client_rate",
            "currency", "is_active", "created_at", "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]

    def get_monthly_hr_cost(self, obj):
        """Indicative monthly cost (22 working days)."""
        return round(float(obj.hr_daily_rate) * 22, 2)

    def get_monthly_client_rate(self, obj):
        return round(float(obj.client_billing_rate) * 22, 2)

    def validate(self, data):
        desig = data.get("designation_ref", getattr(self.instance, "designation_ref", None))
        dept  = data.get("department_ref",  getattr(self.instance, "department_ref",  None))
        qs = RateCard.objects.filter(designation_ref=desig, department_ref=dept)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"Rate card for {desig} / {dept} already exists."
            )
        return data

from .models import LeaveType
from apps.attendance.models import LeavePolicyRule


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaveType
        fields = ["id", "name", "slug", "code", "max_days", "is_paid", "color", "is_active", "created_at", "updated_at"]
        read_only_fields = ["id", "slug", "created_at", "updated_at"]


class LeavePolicyRuleSerializer(serializers.ModelSerializer):
    leave_type_name  = serializers.CharField(source="leave_type.name",  read_only=True)
    leave_type_code  = serializers.CharField(source="leave_type.code",  read_only=True)
    leave_type_color = serializers.CharField(source="leave_type.color", read_only=True)
    is_paid          = serializers.BooleanField(source="leave_type.is_paid", read_only=True)

    class Meta:
        model  = LeavePolicyRule
        fields = [
            "id", "leave_type", "leave_type_name", "leave_type_code",
            "leave_type_color", "is_paid", "total_days", "carry_forward",
            "carry_forward_limit", "applicable_to", "effective_from",
            "effective_to", "loss_of_pay_after", "auto_allocate",
            "notes", "created_at",
        ]
        read_only_fields = ["id", "created_at"]



from .models import Holiday

class HolidaySerializer(serializers.ModelSerializer):
    holiday_type_label = serializers.SerializerMethodField()

    class Meta:
        model  = Holiday
        fields = [
            "id", "name", "date", "year", "holiday_type",
            "holiday_type_label", "description", "is_active",
            "created_at", "updated_at",
            
        ]
        read_only_fields = ["id", "year", "created_at", "updated_at"]
        

    def get_holiday_type_label(self, obj):
        return dict(Holiday._meta.get_field("holiday_type").choices).get(obj.holiday_type, obj.holiday_type)

    def validate(self, data):
        date = data.get("date") or (self.instance.date if self.instance else None)
        if date:
            if isinstance(date, str):
                from datetime import datetime
                try:
                    date = datetime.strptime(date, "%Y-%m-%d").date()
                except ValueError:
                    pass
            data["year"] = date.year
        return data


from .models import ReimbursementConfig
from apps.accounts.models import Employee


class ReimbursementConfigReadSerializer(serializers.ModelSerializer):
    """
    Read-only projection of the singleton ReimbursementConfig.
    Returns the full approver snapshot so the UI never needs a separate employee lookup.
    """
    approver_id   = serializers.UUIDField(source="approver.id",           read_only=True)
    approver_name = serializers.CharField(source="approver.full_name",     read_only=True)
    approver_code = serializers.CharField(source="approver.employee_code", read_only=True)
    approver_email= serializers.EmailField(source="approver.email",        read_only=True)
    configured_by_name = serializers.CharField(
        source="configured_by.full_name", read_only=True, default=None
    )
    is_configured = serializers.SerializerMethodField()

    class Meta:
        model  = ReimbursementConfig
        fields = [
            "id",
            "approver_id", "approver_name", "approver_code", "approver_email",
            "configured_by_name",
            "is_configured",
            "created_at", "updated_at",
        ]
        read_only_fields = fields

    def get_is_configured(self, obj) -> bool:
        return obj.approver_id is not None


class ReimbursementConfigWriteSerializer(serializers.Serializer):
    """
    Write-only contract for configuring the singleton approver.

    Why a plain Serializer, not ModelSerializer?
    ModelSerializer exposes too much: it can create/update arbitrary fields and
    bypasses our `set_approver()` business method.  A plain Serializer is
    explicit about what the client may supply and routes all persistence through
    the model's own atomic method.
    """
    approver = serializers.PrimaryKeyRelatedField(
        queryset=Employee.objects.filter(is_active=True, is_deleted=False),
        error_messages={
            "does_not_exist": "No active employee found with the given ID.",
            "required":       "An approver must be selected.",
        },
    )

    def validate_approver(self, employee):
        """Guard: the approver must be an active, non-deleted employee."""
        if not employee.is_active:
            raise serializers.ValidationError("The selected employee is inactive and cannot be an approver.")
        return employee

    def save(self, configured_by=None):
        """
        Route all persistence through the model's atomic method.
        Returns the persisted (or updated) ReimbursementConfig instance.
        """
        approver_employee = self.validated_data["approver"]
        return ReimbursementConfig.set_approver(
            approver_employee=approver_employee,
            configured_by_employee=configured_by,
        )