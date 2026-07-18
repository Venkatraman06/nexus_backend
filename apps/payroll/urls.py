from django.urls import path
from .views import (
    PayrollListCreateView, PayrollDetailView,
    PayrollApproveView, PayrollMarkPaidView, PayslipPDFView,
    MyPayslipsView, MyPayslipPDFView,
    PayrollGenerateView, PayrollBulkGenerateView,
)

urlpatterns = [
    # Employee self-service — must come BEFORE <uuid:pk> patterns
    path("payroll/my/",                          MyPayslipsView.as_view(),        name="my-payslips"),
    path("payroll/my/<uuid:pk>/payslip-pdf/",    MyPayslipPDFView.as_view(),      name="my-payslip-pdf"),
    # Auto-generate (must come before generic list/detail)
    path("payroll/generate/",                    PayrollGenerateView.as_view(),   name="payroll-generate"),
    path("payroll/generate/bulk/",               PayrollBulkGenerateView.as_view(), name="payroll-bulk-generate"),
    # Admin / PMO CRUD
    path("payroll/",                             PayrollListCreateView.as_view(), name="payroll-list"),
    path("payroll/<uuid:pk>/",                   PayrollDetailView.as_view(),     name="payroll-detail"),
    path("payroll/<uuid:pk>/approve/",           PayrollApproveView.as_view(),    name="payroll-approve"),
    path("payroll/<uuid:pk>/mark-paid/",         PayrollMarkPaidView.as_view(),   name="payroll-mark-paid"),
    path("payroll/<uuid:pk>/payslip-pdf/",       PayslipPDFView.as_view(),        name="payslip-pdf"),
]
