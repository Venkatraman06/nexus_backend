from rest_framework.routers import DefaultRouter

from .views import DocumentViewSet

router = DefaultRouter()
router.register("finance/documents", DocumentViewSet, basename="finance-document")

urlpatterns = router.urls
