from django.urls import path
from .views import (
    TodayAttendanceView, CheckInView, CheckOutView, MonthlyAttendanceView,
    StartBreakView, EndBreakView, AttendanceTrackerView, AttendanceExportView,
    AttendanceOverviewView, EmployeeCalendarView,
    LeaveTypeListView, MyLeaveBalancesView,
    MyLeaveRequestListView, LeaveRequestDetailView, LeaveReviewView,
    AdminLeaveRequestListView,
    AttendanceListView, AttendanceClockInEnableView,
)

urlpatterns = [
    path("attendance/today/",                TodayAttendanceView.as_view(),        name="attendance-today"),
    path("attendance/check-in/",             CheckInView.as_view(),                name="attendance-check-in"),
    path("attendance/check-out/",            CheckOutView.as_view(),               name="attendance-check-out"),
    path("attendance/break/start/",          StartBreakView.as_view(),             name="attendance-break-start"),
    path("attendance/break/end/",            EndBreakView.as_view(),               name="attendance-break-end"),
    path("attendance/monthly/",              MonthlyAttendanceView.as_view(),      name="attendance-monthly"),
    path("attendance/overview/",             AttendanceOverviewView.as_view(),     name="attendance-overview"),
    path("attendance/tracker/",              AttendanceTrackerView.as_view(),      name="attendance-tracker"),
    path("attendance/export/",               AttendanceExportView.as_view(),       name="attendance-export"),
    path("attendance/list/",                 AttendanceListView.as_view(),         name="attendance-list"),
    path("attendance/enable-clockin/",       AttendanceClockInEnableView.as_view(),name="attendance-enable-clockin"),
    path("attendance/employee-calendar/",    EmployeeCalendarView.as_view(),       name="attendance-employee-calendar"),
    path("leave/types/",                     LeaveTypeListView.as_view(),          name="leave-types"),
    path("leave/balances/",                  MyLeaveBalancesView.as_view(),        name="leave-balances"),
    path("leave/requests/",                  MyLeaveRequestListView.as_view(),     name="leave-requests"),
    path("leave/requests/<uuid:pk>/",        LeaveRequestDetailView.as_view(),     name="leave-request-detail"),
    path("leave/requests/<uuid:pk>/review/", LeaveReviewView.as_view(),            name="leave-review"),
    path("leave/admin/requests/",            AdminLeaveRequestListView.as_view(),  name="leave-admin-requests"),
]