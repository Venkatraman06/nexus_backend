from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import serializers

from apps.accounts.serializers import EmployeeListSerializer
from .models import Allocation


class AllocationSerializer(serializers.ModelSerializer):
    employee_name = serializers.SerializerMethodField()
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    designation_name = serializers.CharField(source="employee.designation_ref.name", read_only=True, default=None)
    project_name = serializers.CharField(source="project.name", read_only=True)
    project_code = serializers.CharField(source="project.code", read_only=True)
    daily_hours = serializers.FloatField(read_only=True)

    class Meta:
        model = Allocation
        fields = [
            "id", "employee", "employee_name", "employee_code", "designation_name",
            "project", "project_name", "project_code",
            "allocation_percentage", "daily_hours",
            "start_date", "end_date", "notes",
            "created_at", "updated_at",
        ]

    def get_employee_name(self, obj):
        return obj.employee.full_name if obj.employee else None


class AllocationCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allocation
        fields = [
            "employee", "project", "allocation_percentage",
            "start_date", "end_date", "notes",
        ]

    def validate(self, attrs):
        instance = self.instance or Allocation()
        for key, value in attrs.items():
            setattr(instance, key, value)
        try:
            instance.clean()
        except DjangoValidationError as exc:
            if hasattr(exc, "message_dict"):
                raise serializers.ValidationError(exc.message_dict)
            if hasattr(exc, "messages"):
                raise serializers.ValidationError({"detail": exc.messages})
            raise serializers.ValidationError(str(exc))
        return attrs


class EmployeeCapacitySerializer(serializers.Serializer):
    """Summarises an employee's capacity for a given month."""
    employee_id = serializers.UUIDField()
    employee_name = serializers.CharField()
    month = serializers.CharField()
    working_days = serializers.IntegerField()
    total_capacity_hours = serializers.FloatField()
    allocated_hours = serializers.FloatField()
    logged_hours = serializers.FloatField()
    utilization_percent = serializers.FloatField()
    billing_utilization_percent = serializers.FloatField()
    allocation_percent = serializers.FloatField()
    is_over_allocated = serializers.BooleanField()
