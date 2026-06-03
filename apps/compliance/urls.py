from django.urls import path
from .views import (
    HRComplianceListCreateView, HRComplianceDetailView,
    PolicyDocumentListCreateView, PolicyDocumentDetailView,
)

urlpatterns = [
    path("hr-compliance/",         HRComplianceListCreateView.as_view(), name="hr-compliance-list"),
    path("hr-compliance/<uuid:pk>/", HRComplianceDetailView.as_view(),   name="hr-compliance-detail"),
    path("policy-documents/",         PolicyDocumentListCreateView.as_view(), name="policy-document-list"),
    path("policy-documents/<uuid:pk>/", PolicyDocumentDetailView.as_view(),   name="policy-document-detail"),
]
