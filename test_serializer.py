import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.todos.models import Todo
from apps.todos.serializers import TodoListSerializer, TodoCreateSerializer

todo = Todo.objects.last()
print("Todo list serializer output:", TodoListSerializer(todo).data.get('comments'))
print("Todo create serializer output:", TodoCreateSerializer(todo).data.get('comments'))
