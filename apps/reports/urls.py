from django.urls import path

from .views import (
    EmployeeDailyLogReport,
    EmployeeMonthlyUtilizationReport,
    ProjectProgressReport,
    PMOPortfolioReport,
    AllocationMatrixReport,
)

urlpatterns = [
    path("reports/employee-daily-log/", EmployeeDailyLogReport.as_view(), name="report-daily-log"),
    path("reports/employee-utilization/", EmployeeMonthlyUtilizationReport.as_view(), name="report-utilization"),
    path("reports/project-progress/", ProjectProgressReport.as_view(), name="report-project-progress"),
    path("reports/pmo-portfolio/", PMOPortfolioReport.as_view(), name="report-portfolio"),
    path("reports/allocation-matrix/", AllocationMatrixReport.as_view(), name="report-allocation-matrix"),
]
