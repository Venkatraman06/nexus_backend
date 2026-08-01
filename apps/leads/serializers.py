from rest_framework import serializers
from .models import (
    Lead, LeadActivity, LeadTask, LeadDocument, Client,
    ClientChatRoom, ClientChatMessage,
)
from apps.accounts.models import Employee


class LeadSerializer(serializers.ModelSerializer):
    class Meta:
        model = Lead
        fields = "__all__"


class LeadActivitySerializer(serializers.ModelSerializer):
    lead_name = serializers.ReadOnlyField()

    class Meta:
        model = LeadActivity
        fields = "__all__"


class LeadTaskSerializer(serializers.ModelSerializer):
    lead_name = serializers.ReadOnlyField()

    class Meta:
        model = LeadTask
        fields = "__all__"


class LeadDocumentSerializer(serializers.ModelSerializer):
    lead_name = serializers.ReadOnlyField()

    class Meta:
        model = LeadDocument
        fields = "__all__"


class ClientSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()

    class Meta:
        model = Client
        fields = "__all__"

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.full_name if obj.assigned_to else None


from apps.accounts.models import Employee


class EmployeeMiniSerializer(serializers.ModelSerializer):
    full_name = serializers.ReadOnlyField()

    class Meta:
        model = Employee
        fields = ["id", "full_name", "email", "employee_code"]


class ClientSerializer(serializers.ModelSerializer):
    assigned_to_name = serializers.SerializerMethodField()
    assigned_employees = EmployeeMiniSerializer(many=True, read_only=True)
    assigned_employee_ids = serializers.PrimaryKeyRelatedField(
        source="assigned_employees", queryset=Employee.objects.all(),
        many=True, write_only=True, required=False,
    )

    class Meta:
        model = Client
        fields = "__all__"

    def get_assigned_to_name(self, obj):
        return obj.assigned_to.full_name if obj.assigned_to else None


class ClientChatMessageSerializer(serializers.ModelSerializer):
    sender_name = serializers.SerializerMethodField()

    class Meta:
        model = ClientChatMessage
        fields = ["id", "room", "sender", "sender_name", "text", "created_at"]
        read_only_fields = ["sender", "created_at"]

    def get_sender_name(self, obj):
        return obj.sender.full_name if obj.sender else None


class ClientChatRoomSerializer(serializers.ModelSerializer):
    participants = EmployeeMiniSerializer(many=True, read_only=True)
    client_name = serializers.ReadOnlyField(source="client.name")
    last_message = serializers.SerializerMethodField()
    unread_count = serializers.SerializerMethodField()

    class Meta:
        model = ClientChatRoom
        fields = ["id", "client", "client_name", "name", "participants", "last_message", "unread_count", "created_at"]

    def get_last_message(self, obj):
        msg = obj.messages.order_by("-created_at").first()
        if not msg:
            return None
        return {"text": msg.text, "sender_name": msg.sender.full_name if msg.sender else None, "created_at": msg.created_at}

    def get_unread_count(self, obj):
        # Simple version: no read-tracking yet, always 0. Extend later if needed.
        return 0