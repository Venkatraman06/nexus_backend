from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import ChatSearchView, ConversationViewSet, MessageViewSet

router = DefaultRouter()
router.register("chat/conversations", ConversationViewSet, basename="chat-conversation")
router.register("chat/messages", MessageViewSet, basename="chat-message")

urlpatterns = [
    path("chat/search/", ChatSearchView.as_view(), name="chat-search"),
] + router.urls
