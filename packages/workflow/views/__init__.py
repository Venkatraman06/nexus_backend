from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from rest_framework import status
from rest_framework.decorators import action, api_view
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.common.permissions import IsAuthenticated, HasKeycloakPermission
from packages.workflow.models import State, Transition, WorkflowGroup
from packages.workflow.serializers import (
    WorkflowGroupSerializer,
    StateSerializer,
    TransitionSerializer,
    BulkTransitionItemSerializer,
)


def _resolve_content_type(app_label, model):
    """Return ContentType or None."""
    try:
        return ContentType.objects.get(app_label=app_label, model=model)
    except ContentType.DoesNotExist:
        return None


class WorkflowGroupViewSet(ModelViewSet):
    serializer_class = WorkflowGroupSerializer
    queryset = WorkflowGroup.objects.all()


class WorkflowStateViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {
        "create": "pmt.master.workflow.manage",
        "update": "pmt.master.workflow.manage",
        "partial_update": "pmt.master.workflow.manage",
        "destroy": "pmt.master.workflow.manage",
    }
    serializer_class = StateSerializer

    def get_queryset(self):
        qs = State.objects.select_related("content_type")
        app_label = self.request.query_params.get("app_label")
        model     = self.request.query_params.get("model")
        if app_label and model:
            ct = _resolve_content_type(app_label, model)
            if not ct:
                return qs.none()
            qs = qs.filter(content_type=ct)
        return qs.order_by("order")

    @action(detail=False, methods=["get"], url_path="content-type-id")
    def content_type_id(self, request):
        """Return the numeric ContentType id for a given app_label + model."""
        app_label = request.query_params.get("app_label")
        model     = request.query_params.get("model")
        if not app_label or not model:
            return Response({"error": "app_label and model are required"}, status=status.HTTP_400_BAD_REQUEST)
        ct = _resolve_content_type(app_label, model)
        if not ct:
            return Response({"error": f"ContentType '{app_label}.{model}' not found"}, status=status.HTTP_404_NOT_FOUND)
        return Response({"id": ct.id, "app_label": ct.app_label, "model": ct.model})


class WorkflowTransitionViewSet(ModelViewSet):
    permission_classes = [IsAuthenticated, HasKeycloakPermission]
    PERMISSION_MAP = {
        "create": "pmt.master.workflow.manage",
        "update": "pmt.master.workflow.manage",
        "partial_update": "pmt.master.workflow.manage",
        "destroy": "pmt.master.workflow.manage",
        "bulk_save": "pmt.master.workflow.manage",
    }
    serializer_class = TransitionSerializer

    def get_queryset(self):
        qs = Transition.objects.select_related(
            "content_type", "source_state", "destination_state"
        ).prefetch_related("groups")
        app_label = self.request.query_params.get("app_label")
        model = self.request.query_params.get("model")
        if app_label and model:
            ct = _resolve_content_type(app_label, model)
            if not ct:
                return qs.none()
            qs = qs.filter(content_type=ct)
        return qs

    @action(detail=False, methods=["post"], url_path="bulk-save")
    @transaction.atomic
    def bulk_save(self, request):
        """
        Bulk create/update transitions for a given content type.
        Pass ?app_label=apps.projects&model=project in query params.
        Body: list of transition objects (with optional `id` for updates).
        Transitions NOT in the payload are deleted.
        """
        app_label = request.query_params.get("app_label")
        model = request.query_params.get("model")
        if not app_label or not model:
            return Response(
                {"error": "app_label and model query params are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        ct = _resolve_content_type(app_label, model)
        if not ct:
            return Response(
                {"error": f"ContentType '{app_label}.{model}' not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        items_data = request.data if isinstance(request.data, list) else []
        serializer = BulkTransitionItemSerializer(data=items_data, many=True)
        serializer.is_valid(raise_exception=True)
        validated = serializer.validated_data

        incoming_ids = {str(item["id"]) for item in validated if "id" in item}

        # Delete transitions that are no longer in the payload
        Transition.objects.filter(content_type=ct).exclude(
            id__in=incoming_ids
        ).delete()

        result = []
        for item in validated:
            tid = item.get("id")
            groups = item.pop("groups", [])
            item["content_type"] = ct

            if tid:
                obj, _ = Transition.objects.update_or_create(
                    id=tid, defaults=item
                )
            else:
                obj = Transition.objects.create(**item)

            obj.groups.set(groups)
            result.append(TransitionSerializer(obj).data)

        return Response(result, status=status.HTTP_200_OK)
