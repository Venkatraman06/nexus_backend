from rest_framework.routers import DefaultRouter

from .views import ClientViewSet, ProjectViewSet, ProjectCommentViewSet

router = DefaultRouter()
router.register("clients", ClientViewSet, basename="client")
router.register("projects", ProjectViewSet, basename="project")
router.register("project-comments", ProjectCommentViewSet, basename="project-comment")

urlpatterns = router.urls
