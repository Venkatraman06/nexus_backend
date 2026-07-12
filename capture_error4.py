import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.followups.models import FollowUp
from apps.accounts.models import Employee
from apps.followups.views import FollowUpViewSet
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from packages.workflow.models import State

user = Employee.objects.first()

if not FollowUp.objects.exists():
    print("Creating mock followup")
    FollowUp.objects.create(
        title="Test FollowUp",
        assignee=user,
        reporter=user,
    )

factory = APIRequestFactory()

def test_view(view_func, request):
    req = Request(request)
    req.user = user
    try:
        response = view_func(req)
        # force evaluation of the response
        if hasattr(response, 'render'):
            response.render()
        print("Success:", response.status_code, type(response.data))
    except Exception as e:
        print("Exception:", type(e), e)
        traceback.print_exc()

print("Testing FollowUpViewSet.board (JSON)...")
view = FollowUpViewSet()
# Set format to JSON
request = factory.get('/pmt/api/v1/followups/board/', HTTP_ACCEPT='application/json')
view.request = Request(request)
view.request.user = user
view.format_kwarg = None
view.action = "board"
test_view(lambda req: view.board(req), request)

print("Testing FollowUpViewSet.list (JSON)...")
view_list = FollowUpViewSet()
request_list = factory.get('/pmt/api/v1/followups/', HTTP_ACCEPT='application/json')
view_list.request = Request(request_list)
view_list.request.user = user
view_list.format_kwarg = None
view_list.action = "list"
test_view(lambda req: view_list.list(req), request_list)
