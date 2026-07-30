import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.accounts.models import Employee

ceo_admins = Employee.base_objects.filter(employee_code='HIT-CEO')
for ceo in ceo_admins:
    ceo.is_system_account = True
    ceo.save(update_fields=['is_system_account'])
    print(f"Updated CEO Admin: {ceo.username}")
