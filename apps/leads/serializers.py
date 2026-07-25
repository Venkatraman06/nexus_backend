from rest_framework import serializers
from .models import Lead, LeadActivity, LeadTask, LeadDocument, Client


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