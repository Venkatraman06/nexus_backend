from rest_framework.routers import DefaultRouter
from .views import CompanyExpenseViewSet, EmployeeReimbursementViewSet

router = DefaultRouter()
router.register("expenses", CompanyExpenseViewSet, basename="expense")
router.register("reimbursements", EmployeeReimbursementViewSet, basename="reimbursement")
urlpatterns = router.urls

