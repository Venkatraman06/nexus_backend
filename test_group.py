import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings.base")
django.setup()

from apps.accounts.models import Employee
try:
    dharshini = Employee.objects.get(full_name='Dharshini S')
    print("DHARSHINI GROUP:", dharshini.keycloak_group)
except Exception as e:
    print(e)
