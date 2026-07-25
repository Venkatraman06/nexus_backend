from django.test import RequestFactory
from apps.meetings.views import MeetingViewSet

rf = RequestFactory()
request = rf.get('/api/v1/meetings/')
# we need to authenticate
from apps.accounts.models import User, Employee
user = User.objects.first()
request.user = user

view = MeetingViewSet.as_view({'get': 'list'})
response = view(request)
print(response.data)
