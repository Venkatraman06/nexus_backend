from packages.workflow.models import Proceeding


class ProceedingService:
    @staticmethod
    def get_history(workflow_object):
        return Proceeding.objects.filter(
            object_id=workflow_object.pk
        ).select_related("previous_state", "state", "transitioned_by").order_by("-created_at")
