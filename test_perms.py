import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'core.settings')
django.setup()
from apps.accounts.models import Employee
from packages.keycloak.permissions import PermissionResolver
from packages.keycloak.services import KeycloakService
email = 'ceo@hackersinfotech.com'
user = Employee.objects.filter(username=email).first()
if not user:
    print('User not found')
else:
    print('Django Group:', user.keycloak_group, 'Manager:', user.is_manager, 'PMO:', user.is_pmo)
    print('Keycloak ID:', user.keycloak_id)
    if user.keycloak_id:
        svc = KeycloakService()
        print('KC Groups:', [g['name'] for g in svc.keycloak_admin.get_user_groups(user.keycloak_id)])
        perms = PermissionResolver().resolve_permissions(user.keycloak_id)
        print('Has followup.create?', 'pmt.crm.followup.create' in perms, 'Total Perms:', len(perms))
