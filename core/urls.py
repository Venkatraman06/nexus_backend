from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from core.settings import URL_PREFIX

prefixes = list(set([URL_PREFIX, "bms", "pmt"]))

api_urlpatterns = [
    path("api/v1/", include("apps.accounts.urls")),
    path("api/v1/", include("apps.master.urls")),
    path("api/v1/", include("apps.projects.urls")),
    path("api/v1/", include("apps.workitems.urls")),
    path("api/v1/", include("apps.tickets.urls")),
    path("api/v1/", include("apps.allocation.urls")),
    path("api/v1/", include("apps.timesheets.urls")),
    path("api/v1/", include("apps.dashboard.urls")),
    path("api/v1/", include("apps.reports.urls")),
    path("api/v1/", include("apps.attendance.urls")),
    path("api/v1/", include("apps.payroll.urls")),
    path("api/v1/", include("apps.compliance.urls")),
    path("api/v1/", include("apps.payment.urls")),
    path("api/v1/", include("apps.finance.urls")),
    path("api/v1/", include("apps.expenses.urls")),
    path("api/v1/", include("apps.followups.urls")),
    path("api/v1/", include("apps.leads.urls")),
    path("api/v1/", include("apps.sales.urls")),
    path("api/v1/", include("apps.todos.urls")),
    path("api/v1/", include("apps.workspace.urls")),
    path("api/v1/", include("apps.social_feed.urls")),
    path("api/v1/", include("apps.notifications.urls")),
    path("api/v1/", include("apps.chat.urls")),
]

urlpatterns = []
for pfx in prefixes:
    urlpatterns += [
        path(f"{pfx}/admin/", admin.site.urls),
        path(f"{pfx}/api/schema/", SpectacularAPIView.as_view(), name=f"schema-{pfx}"),
        path(f"{pfx}/api/docs/", SpectacularSwaggerView.as_view(url_name=f"schema-{pfx}"), name=f"swagger-ui-{pfx}"),
        path(f"{pfx}/api/redoc/", SpectacularRedocView.as_view(url_name=f"schema-{pfx}"), name=f"redoc-{pfx}"),
        path(f"{pfx}/", include(api_urlpatterns)),
    ]

# Fallback root-level routes for direct API access
urlpatterns += api_urlpatterns

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
