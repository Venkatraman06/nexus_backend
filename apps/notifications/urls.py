from django.urls import path

from .views import (
    NotificationDashboardView,
    NotificationListView,
    NotificationMarkAllReadView,
    NotificationMarkReadView,
    NotificationUnreadCountView,
)

urlpatterns = [
    path("notifications/", NotificationListView.as_view(), name="notification-list"),
    path("notifications/unread-count/", NotificationUnreadCountView.as_view(), name="notification-unread-count"),
    path("notifications/dashboard/", NotificationDashboardView.as_view(), name="notification-dashboard"),
    path("notifications/read-all/", NotificationMarkAllReadView.as_view(), name="notification-read-all"),
    path("notifications/<uuid:pk>/read/", NotificationMarkReadView.as_view(), name="notification-read"),
]
