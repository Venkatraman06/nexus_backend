from django.urls import path

from .views import WorkspaceCalendarView

urlpatterns = [
    path("workspace/calendar/", WorkspaceCalendarView.as_view(), name="workspace-calendar"),
]
