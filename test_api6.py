from django.test import RequestFactory
from apps.meetings.views import MeetingViewSet

rf = RequestFactory()
request = rf.get('/api/v1/meetings/')
from apps.accounts.models import User
user = User.objects.first()
request.user = user

view = MeetingViewSet.as_view({'get': 'list'})
response = view(request)
print(response.data)
