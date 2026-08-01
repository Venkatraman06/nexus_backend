from rest_framework import serializers
from .models import TrainingCategory, Deal, Quotation


class TrainingCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = TrainingCategory
        fields = "__all__"


class DealSerializer(serializers.ModelSerializer):
    client_name = serializers.ReadOnlyField(source="client.name", default="")
    training_category_name = serializers.ReadOnlyField(source="training_category.name", default="")

    class Meta:
        model = Deal
        fields = "__all__"


class QuotationSerializer(serializers.ModelSerializer):
    client_details = serializers.SerializerMethodField()

    class Meta:
        model = Quotation
        fields = "__all__"

    def get_client_details(self, obj):
        if not obj.client:
            return None
        return {
            "id": obj.client.id,
            "name": obj.client.name,
            "email": obj.client.email or "",
        }
