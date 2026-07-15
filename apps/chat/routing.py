from django.urls import re_path

from core.settings import URL_PREFIX

from .consumers import ChatConsumer

websocket_urlpatterns = [
    re_path(rf"^{URL_PREFIX}/ws/chat/$", ChatConsumer.as_asgi()),
]
