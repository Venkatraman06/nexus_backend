import os
from datetime import date, timedelta
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import TestCase
from apps.followups.serializers import FollowUpCreateSerializer


class ValidationTestCase(TestCase):
    def test_followup_serializer_validation(self):
        today = date.today()
        start = today + timedelta(days=1)
        end = today + timedelta(days=2)
        data = {
            "title": "synclature - Meet",
            "type": "MEETING",
            "priority": "HIGH",
            "description": "Synclature team sync meeting",
            "comments": "",
            "assignees": [],
            "start_date": start.strftime("%Y-%m-%d"),
            "end_date": end.strftime("%Y-%m-%d"),
            "start_time": "10:00:00",
            "end_time": "15:00:00",
            "meeting_mode": "OFFLINE"
        }
        serializer = FollowUpCreateSerializer(data=data)
        self.assertTrue(serializer.is_valid(), f"Errors: {serializer.errors}")


