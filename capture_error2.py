import os
import django
import sys
import traceback

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.followups.views import FollowUpViewSet
from rest_framework.test import APIRequestFactory
from rest_framework.request import Request
from apps.accounts.models import Employee

factory = APIRequestFactory()
user = Employee.objects.first()

def test_view(view_func, request):
    req = Request(request)
    req.user = user
    try:
        response = view_func(req)
        print("Success:", response)
    except Exception as e:
        print("Exception:", e)
        traceback.print_exc()

print("Testing FollowUpViewSet.board...")
view = FollowUpViewSet()
view.request = Request(factory.get('/pmt/api/v1/followups/board/'))
view.request.user = user
view.format_kwarg = None
view.action = "board"
test_view(
    lambda req: view.board(req),
    factory.get('/pmt/api/v1/followups/board/')
)

print("Testing FollowUpViewSet.list...")
view_list = FollowUpViewSet()
view_list.request = Request(factory.get('/pmt/api/v1/followups/'))
view_list.request.user = user
view_list.format_kwarg = None
view_list.action = "list"
test_view(
    lambda req: view_list.list(req),
    factory.get('/pmt/api/v1/followups/')
)
