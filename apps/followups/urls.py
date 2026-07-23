from rest_framework.routers import DefaultRouter

from .views import FollowUpViewSet, MeetingViewSet

router = DefaultRouter()
router.register("followups", FollowUpViewSet, basename="followup")
router.register("meetings", MeetingViewSet, basename="meeting")

urlpatterns = router.urls
