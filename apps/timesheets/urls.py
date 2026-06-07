from django.urls import path

from .views import (
    LoggableDatesView,
    LoggableTicketsView,
    MissingTimesheetView,
    MyTimesheetCopyDayView,
    MyTimesheetCopyWeekView,
    MyTimesheetSubmitView,
    MyTimesheetView,
    MyTimesheetWeekView,
    ReportingApproveView,
    ReportingBulkApproveView,
    ReportingBulkRejectView,
    ReportingDashboardView,
    ReportingRejectView,
    ReportingReviewView,
    TimesheetConfigView,
    TeamTimesheetView,
    UtilizationReportView,
)

urlpatterns = [
    # Employee — My Timesheet
    path("timesheets/my/", MyTimesheetView.as_view(), name="my-timesheet"),
    path("timesheets/my/week/", MyTimesheetWeekView.as_view(), name="my-timesheet-week"),
    path("timesheets/my/submit/<uuid:timesheet_id>/", MyTimesheetSubmitView.as_view(), name="my-timesheet-submit"),
    path("timesheets/my/copy-day/", MyTimesheetCopyDayView.as_view(), name="my-timesheet-copy-day"),
    path("timesheets/my/copy-week/", MyTimesheetCopyWeekView.as_view(), name="my-timesheet-copy-week"),
    path("timesheets/loggable-tickets/", LoggableTicketsView.as_view(), name="loggable-tickets"),
    path("timesheets/loggable-dates/", LoggableDatesView.as_view(), name="loggable-dates"),
    path("timesheets/config/", TimesheetConfigView.as_view(), name="timesheet-config"),

    # Manager — Reporting Timesheet
    path("timesheets/reporting/dashboard/", ReportingDashboardView.as_view(), name="reporting-dashboard"),
    path("timesheets/reporting/review/", ReportingReviewView.as_view(), name="reporting-review"),
    path("timesheets/reporting/approve/", ReportingApproveView.as_view(), name="reporting-approve"),
    path("timesheets/reporting/reject/", ReportingRejectView.as_view(), name="reporting-reject"),
    path("timesheets/reporting/bulk-approve/", ReportingBulkApproveView.as_view(), name="reporting-bulk-approve"),
    path("timesheets/reporting/bulk-reject/", ReportingBulkRejectView.as_view(), name="reporting-bulk-reject"),
    path("timesheets/missing/", MissingTimesheetView.as_view(), name="missing-timesheets"),
    path("timesheets/utilization/", UtilizationReportView.as_view(), name="timesheet-utilization"),

    # Legacy team endpoint
    path("timesheets/team/", TeamTimesheetView.as_view(), name="team-timesheet"),
]
