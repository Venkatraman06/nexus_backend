from django.urls import path
from .views import (
    OffboardingRecordListCreateView, OffboardingRecordDetailView,
    OffboardingPreferenceView,
    ClearanceItemListCreateView, ClearanceItemDetailView,
    ExitInterviewView,
    OffboardingDocumentListCreateView, OffboardingDocumentDetailView,
    OffboardingWorkflowStageListCreateView, OffboardingWorkflowStageDetailView,
    ClearanceOwnerNotifyView, ClearanceReportView,
)

urlpatterns = [
    path("offboarding/", OffboardingRecordListCreateView.as_view(), name="offboarding-list"),
    path("offboarding/<uuid:pk>/", OffboardingRecordDetailView.as_view(), name="offboarding-detail"),

    path("offboarding/<uuid:offboarding_id>/preference/", OffboardingPreferenceView.as_view(), name="offboarding-preference"),

    path("offboarding/<uuid:offboarding_id>/clearance/", ClearanceItemListCreateView.as_view(), name="offboarding-clearance-list"),
    path("offboarding/clearance/<uuid:pk>/", ClearanceItemDetailView.as_view(), name="offboarding-clearance-detail"),

    path("offboarding/<uuid:offboarding_id>/exit-interview/", ExitInterviewView.as_view(), name="offboarding-exit-interview"),

    path("offboarding/<uuid:offboarding_id>/documents/", OffboardingDocumentListCreateView.as_view(), name="offboarding-document-list"),
    path("offboarding/documents/<uuid:pk>/", OffboardingDocumentDetailView.as_view(), name="offboarding-document-detail"),

    path("offboarding/<uuid:offboarding_id>/workflow/", OffboardingWorkflowStageListCreateView.as_view(), name="offboarding-workflow-list"),
    path("offboarding/workflow/<uuid:pk>/", OffboardingWorkflowStageDetailView.as_view(), name="offboarding-workflow-detail"),

    path("offboarding/clearance-notify/", ClearanceOwnerNotifyView.as_view(), name="offboarding-clearance-notify"),
    path("offboarding/clearance-report/", ClearanceReportView.as_view(), name="offboarding-clearance-report"),
]