import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from django.test import Client
from django.conf import settings

client = Client(HTTP_HOST=settings.ALLOWED_HOSTS[0] if settings.ALLOWED_HOSTS else 'localhost')
response = client.get('/pmt/api/v1/projects/')
print("Status code for /pmt/api/v1/projects/:", response.status_code)
