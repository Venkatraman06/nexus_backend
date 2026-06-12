from rest_framework import serializers
from .models import (
    Designation, Department, Location, Grade, EmploymentType,
    ShiftCategory, RateCard, ClientCategory, BusinessType, BillingType,
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
