import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.followups.serializers import FollowUpCreateSerializer

data = {
    "title": "synclature - Meet",
    "type": "MEETING",
    "priority": "HIGH",
    "description": "",
    "comments": "",
    "assignees": [],
    "start_date": "2026-07-21",
    "end_date": "2026-07-22",
    "start_time": "10:00:00",
    "end_time": "15:00:00",
    "meeting_mode": "OFFLINE"
}
serializer = FollowUpCreateSerializer(data=data)
if serializer.is_valid():
    print("Valid!")
else:
    print("Invalid:", serializer.errors)
