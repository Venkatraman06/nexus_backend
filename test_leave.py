import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client
from apps.accounts.models import Employee
from django.conf import settings

client = Client(HTTP_HOST=settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost')
emp = Employee.objects.exclude(is_system_account=True).first()
client.force_login(emp)

response = client.post('/pmt/api/v1/leave/requests/', {
    'leave_type': '11111111-1111-1111-1111-111111111111', # fake UUID
    'start_date': '2026-07-31',
    'end_date': '2026-07-31',
    'reason': 'cold',
    'is_emergency': True
})
print("Status:", response.status_code)
if response.status_code >= 400:
    print(response.content.decode()[:500])
