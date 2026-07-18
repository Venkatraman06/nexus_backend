from rest_framework.routers import DefaultRouter

from .views import WorkLogViewSet
from packages.workflow.views import (
    WorkflowGroupViewSet,
    WorkflowStateViewSet,
    WorkflowTransitionViewSet,
)

router = DefaultRouter()
router.register("work-logs", WorkLogViewSet, basename="worklog")
router.register("workflow/groups", WorkflowGroupViewSet, basename="workflow-group")
router.register("workflow/states", WorkflowStateViewSet, basename="workflow-state")
router.register("workflow/transitions", WorkflowTransitionViewSet, basename="workflow-transition")

urlpatterns = router.urls
