import os
import django
import json

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.todos.views import TodoViewSet
from apps.todos.models import Todo
from rest_framework.test import APIRequestFactory, force_authenticate
from django.contrib.auth import get_user_model

User = get_user_model()
user = User.objects.first()
todo = Todo.objects.last()

factory = APIRequestFactory()
request = factory.patch(f"/pmt/api/v1/todos/{todo.id}/", data=json.dumps({"comments": "Dharshini S (22 Jul 2026, 06:30 PM):\nhi"}), content_type="application/json")
force_authenticate(request, user=user)

# We need to mock _can_view_all and HasKeycloakPermission if they fail
from rest_framework.permissions import AllowAny
TodoViewSet.permission_classes = [AllowAny]

view = TodoViewSet.as_view({'patch': 'partial_update'})
response = view(request, pk=todo.id)

print("Status:", response.status_code)
print("Data:", response.data)

todo.refresh_from_db()
print("DB comments:", repr(todo.comments))
