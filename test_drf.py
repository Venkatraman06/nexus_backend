import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from rest_framework import serializers

class MockState:
    def __init__(self, name):
        self.name = name

class MockObj:
    def __init__(self, state):
        self.workflow_state = state

class MockSerializer(serializers.Serializer):
    name = serializers.CharField(source="workflow_state.name", read_only=True, default="")

try:
    print(MockSerializer(MockObj(MockState("test"))).data)
    print(MockSerializer(MockObj(None)).data)
except Exception as e:
    traceback.print_exc()

