import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.accounts.models import Employee
from apps.dashboard.views import EmployeeDashboardView
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request

user = Employee.objects.first()

factory = APIRequestFactory()

def test_view(view_func, request):
    req = Request(request)
    req.user = user
    try:
        response = view_func(req)
        if hasattr(response, 'render'):
            response.render()
        print("Success:", response.status_code)
    except Exception as e:
        print("Exception:", type(e), e)
        traceback.print_exc()

print("Testing EmployeeDashboardView...")
view = EmployeeDashboardView()
request = factory.get('/pmt/api/v1/dashboard/employee/', HTTP_ACCEPT='application/json')
view.request = Request(request)
view.request.user = user
view.format_kwarg = None
test_view(lambda req: view.get(req), request)
