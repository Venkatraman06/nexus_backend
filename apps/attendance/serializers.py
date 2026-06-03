from rest_framework import serializers
from .models import AttendanceRecord, AttendanceBreak, LeaveType, LeaveBalance, LeaveRequest


class AttendanceBreakSerializer(serializers.ModelSerializer):
    duration_minutes = serializers.ReadOnlyField()
    break_type_label = serializers.SerializerMethodField()

    class Meta:
        model  = AttendanceBreak
        fields = ["id", "break_type", "break_type_label", "start_time", "end_time", "duration_minutes"]

    def get_break_type_label(self, obj):
        return obj.get_break_type_display()


class AttendanceRecordSerializer(serializers.ModelSerializer):
    duration_hours      = serializers.ReadOnlyField()
    working_hours       = serializers.ReadOnlyField()
    total_break_minutes = serializers.ReadOnlyField()
    breaks              = AttendanceBreakSerializer(many=True, read_only=True)

    class Meta:
        model  = AttendanceRecord
        fields = [
            "id", "date", "check_in", "check_out", "status", "notes",
            "check_in_lat", "check_in_lng", "check_out_lat", "check_out_lng",
            "duration_hours", "working_hours", "total_break_minutes",
            "breaks", "created_at",
        ]
        read_only_fields = ["id", "created_at"]


class CheckInSerializer(serializers.Serializer):
    notes  = serializers.CharField(required=False, allow_blank=True, default="")
    status = serializers.ChoiceField(choices=["PRESENT", "WFH"], default="PRESENT")
    lat    = serializers.FloatField(required=False, allow_null=True, default=None)
    lng    = serializers.FloatField(required=False, allow_null=True, default=None)


class CheckOutSerializer(serializers.Serializer):
    notes = serializers.CharField(required=False, allow_blank=True, default="")
    lat   = serializers.FloatField(required=False, allow_null=True, default=None)
    lng   = serializers.FloatField(required=False, allow_null=True, default=None)


class StartBreakSerializer(serializers.Serializer):
    break_type = serializers.ChoiceField(choices=["TEA", "LUNCH", "OTHER"], default="OTHER")


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model  = LeaveType
        fields = ["id", "name", "code", "max_days", "is_paid", "color"]


class LeaveBalanceSerializer(serializers.ModelSerializer):
    leave_type_name  = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_code  = serializers.CharField(source="leave_type.code", read_only=True)
    leave_type_color = serializers.CharField(source="leave_type.color", read_only=True)
    is_paid          = serializers.BooleanField(source="leave_type.is_paid", read_only=True)
    pending_days     = serializers.SerializerMethodField()
    remaining_days   = serializers.SerializerMethodField()

    class Meta:
        model  = LeaveBalance
        fields = [
            "id", "leave_type_name", "leave_type_code", "leave_type_color",
            "is_paid", "year", "total_days", "used_days", "pending_days", "remaining_days",
        ]

    def get_pending_days(self, obj):
        return obj.pending_days

    def get_remaining_days(self, obj):
        return obj.remaining_days


class LeaveRequestSerializer(serializers.ModelSerializer):
    leave_type_name  = serializers.CharField(source="leave_type.name", read_only=True)
    leave_type_color = serializers.CharField(source="leave_type.color", read_only=True)
    reviewer_name    = serializers.SerializerMethodField()

    class Meta:
        model  = LeaveRequest
        fields = [
            "id", "leave_type", "leave_type_name", "leave_type_color",
            "start_date", "end_date", "days_count", "status",
            "reason", "reviewer_name", "reviewer_remarks", "created_at",
        ]
        read_only_fields = ["id", "days_count", "status", "reviewer_name", "reviewer_remarks", "created_at"]

    def get_reviewer_name(self, obj):
        return obj.reviewer.full_name if obj.reviewer_id else None

    def validate(self, data):
        if data.get("end_date") and data.get("start_date"):
            if data["end_date"] < data["start_date"]:
                raise serializers.ValidationError("end_date must be ≥ start_date")
        return data


class LeaveReviewSerializer(serializers.Serializer):
    status  = serializers.ChoiceField(choices=["APPROVED", "REJECTED"])
    remarks = serializers.CharField(required=False, allow_blank=True, default="")
