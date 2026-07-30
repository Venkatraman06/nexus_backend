import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()

from apps.accounts.models import Employee

ceo = Employee.base_objects.filter(employee_code='HIT-CEO').first()
if ceo:
    ceo.is_system_account = True
    ceo.save(update_fields=['is_system_account'])
    print(f"Found by HIT-CEO and updated: {ceo.username}")
else:
    print("Could not find by HIT-CEO. Finding all users...")
    for emp in Employee.base_objects.all():
        print(f"Emp: {emp.username}, code: {emp.employee_code}, name: {emp.first_name} {emp.last_name}")
        if emp.first_name == 'CEO' and emp.last_name == 'Admin':
            emp.is_system_account = True
            emp.save(update_fields=['is_system_account'])
            print(f"Updated CEO Admin: {emp.username}")
