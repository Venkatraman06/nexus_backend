import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.accounts.models import Employee

print("Total base_objects:", Employee.base_objects.count())
print("Total objects (excluding system account):", Employee.objects.count())

system_accounts = Employee.base_objects.filter(is_system_account=True).count()
print("System accounts count:", system_accounts)
