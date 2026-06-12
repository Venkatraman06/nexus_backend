from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import (
    MilestoneViewSet,
    InvoiceViewSet,
    PaymentViewSet,
    PaymentAllocationViewSet,
    PaymentDashboardView,
    ClientReceivableView,
    ProjectReceivableView,
)

router = DefaultRouter()
router.register("payment/milestones",   MilestoneViewSet,         basename="payment-milestone")
router.register("payment/invoices",     InvoiceViewSet,           basename="payment-invoice")
router.register("payment/payments",     PaymentViewSet,           basename="payment-payment")
router.register("payment/allocations",  PaymentAllocationViewSet, basename="payment-allocation")

urlpatterns = router.urls + [
    path("payment/dashboard/",            PaymentDashboardView.as_view(),   name="payment-dashboard"),
    path("payment/reports/client/",       ClientReceivableView.as_view(),   name="payment-client-receivable"),
    path("payment/reports/project/",      ProjectReceivableView.as_view(),  name="payment-project-receivable"),
]
