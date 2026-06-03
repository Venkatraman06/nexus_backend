from django.urls import path

from .views import MyTimesheetView, TimesheetWeeklyView, TeamTimesheetView

urlpatterns = [
    path("timesheets/my/", MyTimesheetView.as_view(), name="my-timesheet"),
    path("timesheets/weekly/", TimesheetWeeklyView.as_view(), name="timesheet-weekly"),
    path("timesheets/team/", TeamTimesheetView.as_view(), name="team-timesheet"),
]
