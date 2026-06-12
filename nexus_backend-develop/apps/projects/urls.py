from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, ProjectViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("projects", ProjectViewSet, basename="project")

urlpatterns = router.urls
