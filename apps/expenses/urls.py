from rest_framework.routers import DefaultRouter
from .views import CompanyExpenseViewSet

router = DefaultRouter()
router.register("expenses", CompanyExpenseViewSet, basename="expense")
urlpatterns = router.urls
