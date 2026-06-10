from rest_framework.routers import DefaultRouter

from .views import SocialPostViewSet

router = DefaultRouter()
router.register("social-feed", SocialPostViewSet, basename="social-feed")

urlpatterns = router.urls
