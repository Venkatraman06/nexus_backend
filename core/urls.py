from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView, SpectacularRedocView

from core.settings import URL_PREFIX

urlpatterns = [
    path(f"{URL_PREFIX}/admin/", admin.site.urls),
    path(f"{URL_PREFIX}/api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(f"{URL_PREFIX}/api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path(f"{URL_PREFIX}/api/redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
    path(f"{URL_PREFIX}/api/v1/", include("apps.accounts.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.master.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.projects.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.workitems.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.tickets.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.allocation.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.timesheets.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.dashboard.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.reports.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.attendance.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.payroll.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.compliance.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.payment.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.finance.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.expenses.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.followups.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.social_feed.urls")),
    path(f"{URL_PREFIX}/api/v1/", include("apps.notifications.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
