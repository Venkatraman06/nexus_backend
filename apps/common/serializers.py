from rest_framework import serializers


class BaseModelSerializer(serializers.ModelSerializer):
    created_by_name = serializers.SerializerMethodField(read_only=True)
    updated_by_name = serializers.SerializerMethodField(read_only=True)

    def get_created_by_name(self, obj):
        user = getattr(obj, "created_by", None)
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return None

    def get_updated_by_name(self, obj):
        user = getattr(obj, "updated_by", None)
        if user:
            return f"{user.first_name} {user.last_name}".strip() or user.username
        return None
