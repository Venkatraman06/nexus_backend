import re

from rest_framework import serializers

from apps.accounts.serializers import EmployeeDropdownSerializer
from apps.common.validators import validate_phone
from .models import Client, Project, ProjectHistory

_PAN_RE  = re.compile(r'^[A-Z]{5}[0-9]{4}[A-Z]$')
_GST_RE  = re.compile(r'^\d{2}[A-Z]{5}\d{4}[A-Z][1-9A-Z]Z[0-9A-Z]$')


class ClientSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source="category.name", read_only=True, default="")

    class Meta:
        model = Client
        fields = [
            "id", "name", "code", "industry",
            "contact_email", "contact_person", "phone", "address",
            "pan_number", "gst_number",
            "category", "category_name",
            "latitude", "longitude", "formatted_address",
            "is_active", "created_at", "updated_at",
        ]

    def validate_phone(self, value: str) -> str:
        return validate_phone(value, "Phone number")

    def validate_pan_number(self, value: str) -> str:
        if not value:
            return value
        value = value.strip().upper()
        if not _PAN_RE.match(value):
            raise serializers.ValidationError(
                "Invalid PAN format. Expected format: ABCDE1234F"
            )
        qs = Client.objects.filter(pan_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This PAN number is already registered.")
        return value

    def validate_gst_number(self, value: str) -> str:
        if not value:
            return value
        value = value.strip().upper()
        if not _GST_RE.match(value):
            raise serializers.ValidationError(
                "Invalid GSTIN format. Expected format: 22ABCDE1234F1Z5"
            )
        qs = Client.objects.filter(gst_number=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("This GSTIN is already registered.")
        return value


class ClientDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ["id", "name", "code"]


class ProjectDropdownSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = ["id", "name", "code"]


class ProjectListSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True, default="")
    manager_name = serializers.SerializerMethodField()
    logged_hours = serializers.FloatField(read_only=True)
    business_type_name = serializers.CharField(source="business_type.name", read_only=True, default="")
    billing_type_name = serializers.CharField(source="billing_type.name", read_only=True, default="")
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")

    class Meta:
        model = Project
        fields = [
            "id", "name", "code", "description",
            "client", "client_name",
            "business_type", "business_type_name",
            "billing_type", "billing_type_name",
            "is_active",
            "start_date", "end_date", "estimated_hours", "budget", "logged_hours",
            "manager", "manager_name",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "created_at",
        ]

    def get_manager_name(self, obj):
        mgr = obj.manager
        return mgr.full_name if mgr else None


class ProjectDetailSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True, default="")
    manager_name = serializers.SerializerMethodField()
    logged_hours = serializers.FloatField(read_only=True)
    remaining_hours = serializers.FloatField(read_only=True)
    business_type_name = serializers.CharField(source="business_type.name", read_only=True, default="")
    billing_type_name = serializers.CharField(source="billing_type.name", read_only=True, default="")
    workflow_state_name = serializers.CharField(source="workflow_state.name", read_only=True, default="")
    workflow_state_slug = serializers.CharField(source="workflow_state.slug", read_only=True, default="")
    workflow_state_color = serializers.CharField(source="workflow_state.color_code", read_only=True, default="")

    class Meta:
        model = Project
        fields = [
            "id", "name", "code", "description",
            "client", "client_name",
            "business_type", "business_type_name",
            "billing_type", "billing_type_name",
            "is_active",
            "start_date", "end_date", "estimated_hours", "budget", "logged_hours",
            "remaining_hours", "manager", "manager_name",
            "workflow_state", "workflow_state_name", "workflow_state_slug", "workflow_state_color",
            "created_at", "updated_at",
        ]

    def get_manager_name(self, obj):
        mgr = obj.manager
        return mgr.full_name if mgr else None


class ProjectCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model = Project
        fields = [
            "name", "code", "description", "client",
            "business_type", "billing_type", "is_active",
            "start_date", "end_date", "estimated_hours", "budget", "manager",
        ]

    def validate_code(self, value: str) -> str:
        value = value.strip().upper()
        qs = Project.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError("A project with this code already exists.")
        return value

    def update(self, instance, validated_data):
        # These fields are immutable after creation
        for locked in ("code", "business_type", "billing_type"):
            validated_data.pop(locked, None)
        return super().update(instance, validated_data)


class ProjectTransitionSerializer(serializers.Serializer):
    destination_state = serializers.CharField(required=True)
    comments = serializers.CharField(required=False, default="", allow_blank=True)
    manager = serializers.UUIDField(required=False, allow_null=True)


class ProjectHistorySerializer(serializers.ModelSerializer):
    changed_by_name = serializers.SerializerMethodField()
    changed_by_avatar = serializers.SerializerMethodField()

    class Meta:
        model = ProjectHistory
        fields = ["id", "action", "changes", "changed_by_name", "changed_by_avatar", "changed_at"]

    def get_changed_by_name(self, obj):
        if obj.changed_by:
            return obj.changed_by.full_name
        return "System"

    def get_changed_by_avatar(self, obj):
        if not obj.changed_by:
            return None
        try:
            return obj.changed_by.profile_picture.url if obj.changed_by.profile_picture else None
        except Exception:
            return None
