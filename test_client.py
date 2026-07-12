import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from django.test import Client
from apps.accounts.models import Employee

client = Client()
user = Employee.objects.first()
client.force_login(user)

print("Testing workspace calendar...")
res1 = client.get('/pmt/api/v1/workspace/calendar/?date_from=2026-06-28&date_to=2026-08-01')
if res1.status_code != 200:
    print(res1.status_code)
    try:
        print(res1.json())
    except:
        print(res1.content)

print("Testing followups board...")
res2 = client.get('/pmt/api/v1/followups/board/')
if res2.status_code != 200:
    print(res2.status_code)
    try:
        print(res2.json())
    except:
        print(res2.content)

print("Testing followups list...")
res3 = client.get('/pmt/api/v1/followups/')
if res3.status_code != 200:
    print(res3.status_code)
    try:
        print(res3.json())
    except:
        print(res3.content)
