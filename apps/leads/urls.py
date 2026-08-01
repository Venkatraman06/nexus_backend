from rest_framework.routers import DefaultRouter
from .views import (
    LeadViewSet, LeadActivityViewSet, LeadTaskViewSet, LeadDocumentViewSet,
    ClientViewSet, ClientChatRoomViewSet, ClientChatMessageViewSet,
)

router = DefaultRouter()
router.register("leads", LeadViewSet, basename="lead")
router.register("activities", LeadActivityViewSet, basename="lead-activity")
router.register("lead-tasks", LeadTaskViewSet, basename="lead-task")
router.register("lead-documents", LeadDocumentViewSet, basename="lead-document")
router.register("clients", ClientViewSet, basename="crm-client")
router.register("client-chat-rooms", ClientChatRoomViewSet, basename="client-chat-room")
router.register("client-chat-messages", ClientChatMessageViewSet, basename="client-chat-message")

urlpatterns = router.urls