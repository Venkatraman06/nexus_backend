import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.conf import settings
settings.ALLOWED_HOSTS = ['testserver']

from django.test import Client
from apps.todos.models import Todo
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()
todo = Todo.objects.last()

client = Client()
client.force_login(user)

response = client.patch(f"/pmt/api/v1/todos/{todo.id}/", data=json.dumps({"comments": "New patched comment"}), content_type="application/json")
print("Response status:", response.status_code)
print("Response data:", response.json())

todo.refresh_from_db()
print("DB comments:", repr(todo.comments))
