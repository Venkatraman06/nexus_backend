import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import RequestFactory
from apps.meetings.views import MeetingViewSet
from apps.accounts.models import Employee
from apps.meetings.models import Meeting

factory = RequestFactory()
user = Employee.objects.first()

request = factory.get('/api/v1/meetings/board/', {'meeting_mode': 'ONLINE'})
request.user = user
view = MeetingViewSet.as_view({'get': 'board'})
response = view(request)
print("ONLINE mode columns:", list(response.data['columns'].keys()))

request2 = factory.get('/api/v1/meetings/board/', {'status': 'planning'})
request2.user = user
response2 = view(request2)
print("Planning status columns:", list(response2.data['columns'].keys()))
