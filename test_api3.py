import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['testserver']

from django.test import Client
from apps.todos.models import Todo
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()

client = Client()
client.force_login(user)
response = client.get("/pmt/api/v1/todos/board/")
print(response.json())
