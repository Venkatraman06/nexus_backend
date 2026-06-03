from django.urls import path

from .views import PMODashboardView, UtilizationHeatmapView, EmployeeDashboardView, HRMSDashboardView, ProjectHealthView

urlpatterns = [
    path("dashboard/pmo/",                PMODashboardView.as_view(),        name="pmo-dashboard"),
    path("dashboard/hrms/",               HRMSDashboardView.as_view(),       name="hrms-dashboard"),
    path("dashboard/employee/",           EmployeeDashboardView.as_view(),   name="employee-dashboard"),
    path("dashboard/utilization-heatmap/", UtilizationHeatmapView.as_view(), name="utilization-heatmap"),
    path("dashboard/project-health/",     ProjectHealthView.as_view(),       name="project-health"),
]
