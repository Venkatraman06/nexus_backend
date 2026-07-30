from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from core.settings import URL_PREFIX

def build_api_patterns(prefix=""):
    p = f"{prefix}/" if prefix else ""
    return [
        path(f"{p}api/v1/", include("apps.accounts.urls")),
        path(f"{p}api/v1/", include("apps.master.urls")),
        path(f"{p}api/v1/", include("apps.projects.urls")),
        path(f"{p}api/v1/", include("apps.workitems.urls")),
        path(f"{p}api/v1/", include("apps.tickets.urls")),
        path(f"{p}api/v1/", include("apps.allocation.urls")),
        path(f"{p}api/v1/", include("apps.timesheets.urls")),
        path(f"{p}api/v1/", include("apps.dashboard.urls")),
        path(f"{p}api/v1/", include("apps.reports.urls")),
        path(f"{p}api/v1/", include("apps.attendance.urls")),
        path(f"{p}api/v1/", include("apps.payroll.urls")),
        path(f"{p}api/v1/", include("apps.compliance.urls")),
        path(f"{p}api/v1/", include("apps.payment.urls")),
        path(f"{p}api/v1/", include("apps.finance.urls")),
        path(f"{p}api/v1/", include("apps.expenses.urls")),
        path(f"{p}api/v1/", include("apps.followups.urls")),
        path(f"{p}api/v1/", include("apps.meetings.urls")),
        path(f"{p}api/v1/", include("apps.todos.urls")),
        path(f"{p}api/v1/", include("apps.workspace.urls")),
        path(f"{p}api/v1/", include("apps.social_feed.urls")),
        path(f"{p}api/v1/", include("apps.notifications.urls")),
        path(f"{p}api/v1/", include("apps.chat.urls")),
    ]

urlpatterns = [
    path(f"{URL_PREFIX}/admin/", admin.site.urls),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]

# Support pmt, bms, and root prefix so all incoming paths match smoothly
prefixes = set([URL_PREFIX.strip("/"), "pmt", "bms", ""])
for pref in prefixes:
    urlpatterns.extend(build_api_patterns(pref))

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
