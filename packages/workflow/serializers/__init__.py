from django.contrib.contenttypes.models import ContentType
from rest_framework import serializers

from packages.workflow.models import State, Transition, WorkflowGroup


class WorkflowGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowGroup
        fields = ["id", "name", "slug", "description", "created_at"]
        read_only_fields = ["id", "slug", "created_at"]


# ── State ──────────────────────────────────────────────────────────────────────

class StateSerializer(serializers.ModelSerializer):
    content_type_label = serializers.SerializerMethodField(read_only=True)
    # slug and label are auto-generated in State.save(); never required from the API caller
    slug  = serializers.SlugField(read_only=True)
    label = serializers.CharField(read_only=True)

    class Meta:
        model = State
        fields = [
            "id", "name", "slug", "label", "color_code",
            "content_type", "content_type_label",
            "order", "is_initial", "is_final",
        ]
        read_only_fields = ["id", "slug", "label"]

    def get_content_type_label(self, obj):
        if obj.content_type:
            return f"{obj.content_type.app_label}.{obj.content_type.model}"
        return None


# ── Transition ─────────────────────────────────────────────────────────────────

class TransitionGroupSerializer(serializers.ModelSerializer):
    class Meta:
        model = WorkflowGroup
        fields = ["id", "name", "slug"]


class TransitionStateSerializer(serializers.ModelSerializer):
    class Meta:
        model = State
        fields = ["id", "name", "slug", "color_code", "order"]


class TransitionSerializer(serializers.ModelSerializer):
    """
    Create/update transitions.
    Accepts groups as UUIDs (legacy) OR keycloak_group_names as strings.
    keycloak_group_names auto-creates WorkflowGroup entries as needed.
    """
    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=WorkflowGroup.objects.all(), required=False
    )
    # Write-only: accept Keycloak group names and auto-create WorkflowGroup entries
    keycloak_group_names = serializers.ListField(
        child=serializers.CharField(max_length=100),
        write_only=True, required=False,
    )
    # Read-only: return group names as strings for easy frontend consumption
    group_names = serializers.SerializerMethodField(read_only=True)

    source_state_detail  = TransitionStateSerializer(source="source_state",  read_only=True)
    destination_state_detail = TransitionStateSerializer(source="destination_state", read_only=True)
    group_details        = TransitionGroupSerializer(source="groups", many=True, read_only=True)

    class Meta:
        model = Transition
        fields = [
            "id", "content_type", "source_state", "destination_state",
            "label", "groups", "keycloak_group_names", "group_names", "position",
            "source_state_detail", "destination_state_detail", "group_details",
        ]
        read_only_fields = ["id"]

    def get_group_names(self, obj):
        return [g.name for g in obj.groups.all()]

    def _resolve_groups(self, names: list) -> list:
        from django.utils.text import slugify as _slug
        result = []
        for name in names:
            obj, _ = WorkflowGroup.objects.get_or_create(
                name=name,
                defaults={"slug": _slug(name) or _slug(f"group-{name}")},
            )
            result.append(obj)
        return result

    def create(self, validated_data):
        kc_names = validated_data.pop("keycloak_group_names", None)
        groups   = validated_data.pop("groups", [])
        instance = super().create(validated_data)
        instance.groups.set(self._resolve_groups(kc_names) if kc_names is not None else groups)
        return instance

    def update(self, instance, validated_data):
        kc_names = validated_data.pop("keycloak_group_names", None)
        groups   = validated_data.pop("groups", None)
        instance = super().update(instance, validated_data)
        if kc_names is not None:
            instance.groups.set(self._resolve_groups(kc_names))
        elif groups is not None:
            instance.groups.set(groups)
        # Clear cached M2M so group_names reflects the latest mapping in the response
        if hasattr(instance, "_prefetched_objects_cache"):
            instance._prefetched_objects_cache.pop("groups", None)
        return instance


# ── Bulk Transition ────────────────────────────────────────────────────────────

class BulkTransitionItemSerializer(serializers.Serializer):
    id = serializers.UUIDField(required=False)
    source_state = serializers.PrimaryKeyRelatedField(
        queryset=State.objects.all(), allow_null=True, required=False
    )
    destination_state = serializers.PrimaryKeyRelatedField(queryset=State.objects.all())
    label = serializers.CharField(max_length=100, required=False, default="", allow_blank=True)
    groups = serializers.PrimaryKeyRelatedField(
        many=True, queryset=WorkflowGroup.objects.all(), required=False
    )
    position = serializers.JSONField(required=False, default=dict)
