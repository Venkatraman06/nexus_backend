import os
import django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")
django.setup()

from apps.workspace.views import WorkspaceCalendarView
from apps.followups.views import FollowUpViewSet
from rest_framework.test import APIRequestFactory

factory = APIRequestFactory()

request = factory.get('/pmt/api/v1/workspace/calendar/?date_from=2026-06-28&date_to=2026-08-01')
# We need a user.
from apps.accounts.models import Employee
user = Employee.objects.first()
from rest_framework.request import Request
request = Request(request)
request.user = user

view = WorkspaceCalendarView()
try:
    print(view.get(request))
except Exception as e:
    import traceback
    traceback.print_exc()

request2 = factory.get('/pmt/api/v1/followups/board/')
request2 = Request(request2)
request2.user = user
view2 = FollowUpViewSet()
view2.request = request2
view2.format_kwarg = None
try:
    print(view2.board(request2))
except Exception as e:
    import traceback
    traceback.print_exc()

