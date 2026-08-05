import requests
import json

# Assuming we can just hit the API if it doesn't need auth, or we can use the django test client
from django.test import Client
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.todos.models import Todo
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()

todo = Todo.objects.last()
print("Before:", repr(todo.comments))

client = Client()
client.force_login(user)

response = client.patch(f"/pmt/api/v1/todos/{todo.id}/", data=json.dumps({"comments": "New comment from test"}), content_type="application/json")
print(response.status_code, response.json())

todo.refresh_from_db()
print("After:", repr(todo.comments))
