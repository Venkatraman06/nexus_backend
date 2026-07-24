import django_filters
from django.db.models import Q

from .models import FollowUp


class FollowUpFilter(django_filters.FilterSet):
    type = django_filters.CharFilter(field_name="type")
    priority = django_filters.CharFilter(field_name="priority")
    assignee = django_filters.UUIDFilter(field_name="assignees__id")
    reporter = django_filters.UUIDFilter(field_name="reporter_id")
    status = django_filters.CharFilter(field_name="workflow_state__slug")
    due_date_from = django_filters.DateFilter(method="filter_due_date_from")
    due_date_to = django_filters.DateFilter(method="filter_due_date_to")
    start_date = django_filters.DateFilter(method="filter_due_date_from")
    end_date = django_filters.DateFilter(method="filter_due_date_to")
    overdue = django_filters.BooleanFilter(method="filter_overdue")

    class Meta:
        model = FollowUp
        fields = ["type", "priority", "assignee", "reporter", "status"]

    def filter_due_date_from(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(end_date__gte=value) |
            Q(end_date__isnull=True, start_date__gte=value)
        )

    def filter_due_date_to(self, queryset, name, value):
        if not value:
            return queryset
        return queryset.filter(
            Q(start_date__lte=value) |
            Q(start_date__isnull=True, end_date__lte=value)
        )

    def filter_overdue(self, queryset, name, value):
        from datetime import date
        today = date.today()
        if value:
            return queryset.filter(
                end_date__lt=today,
                workflow_state__is_final=False,
            )
        return queryset.exclude(
            end_date__lt=today,
            workflow_state__is_final=False,
        )
