import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.accounts.models import Employee
from apps.notifications.models import Notification

ceo = Employee.base_objects.get(employee_code='HIT-CEO')
print("CEO:", ceo)

qs = Notification.objects.filter(recipient=ceo)
print("Notifs:", qs.count())

