from django.utils import timezone
from drf_spectacular.utils import extend_schema, OpenApiParameter
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.common.permissions import IsAuthenticated
from apps.notifications.models import Notification
from apps.notifications.serializers import MarkReadSerializer, NotificationSerializer


class NotificationListView(APIView):
    """List notifications for the current user. Unread only by default."""

    permission_classes = [IsAuthenticated]

    @extend_schema(
        tags=["Notifications"],
        parameters=[
            OpenApiParameter("unread_only", bool, description="Default true"),
            OpenApiParameter("limit", int, description="Max results (default 50)"),
        ],
        responses={200: NotificationSerializer(many=True)},
    )
    def get(self, request):
        unread_only = request.query_params.get("unread_only", "true").lower() != "false"
        limit = min(int(request.query_params.get("limit", 50)), 100)

        qs = Notification.objects.filter(recipient=request.user)
        if unread_only:
            qs = qs.filter(is_read=False)
        qs = qs.select_related("actor")[:limit]

        return Response(NotificationSerializer(qs, many=True).data)


class NotificationUnreadCountView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notifications"])
    def get(self, request):
        count = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()
        return Response({"unread_count": count})


class NotificationMarkReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notifications"], request=MarkReadSerializer)
    def post(self, request, pk=None):
        if pk:
            try:
                notif = Notification.objects.get(pk=pk, recipient=request.user)
            except Notification.DoesNotExist:
                return Response(status=status.HTTP_404_NOT_FOUND)
            notif.mark_read()
            return Response({"message": "Marked as read."})

        ids = request.data.get("ids", [])
        if ids:
            now = timezone.now()
            updated = Notification.objects.filter(
                recipient=request.user, id__in=ids, is_read=False,
            ).update(is_read=True, read_at=now)
            return Response({"message": f"Marked {updated} as read."})

        return Response({"error": "Provide notification id or ids list."}, status=400)


class NotificationMarkAllReadView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notifications"])
    def post(self, request):
        now = timezone.now()
        updated = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).update(is_read=True, read_at=now)
        return Response({"message": f"Marked {updated} as read."})


class NotificationDashboardView(APIView):
    """Grouped unread summary for billboard / dashboard widgets."""

    permission_classes = [IsAuthenticated]

    @extend_schema(tags=["Notifications"])
    def get(self, request):
        counts = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).count()
        recent = Notification.objects.filter(
            recipient=request.user, is_read=False,
        ).select_related("actor").order_by("-created_at")[:20]

        by_severity = {"info": 0, "warning": 0, "urgent": 0}
        for n in recent:
            by_severity[n.severity] = by_severity.get(n.severity, 0) + 1

        return Response({
            "unread_count": counts,
            "by_severity": by_severity,
            "recent": NotificationSerializer(recent, many=True).data,
        })
