import django_filters

from .models import FollowUp


class FollowUpFilter(django_filters.FilterSet):
    type = django_filters.CharFilter(field_name="type")
    priority = django_filters.CharFilter(field_name="priority")
    assignee = django_filters.UUIDFilter(field_name="assignee_id")
    reporter = django_filters.UUIDFilter(field_name="reporter_id")
    status = django_filters.CharFilter(field_name="workflow_state__slug")
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")
    overdue = django_filters.BooleanFilter(method="filter_overdue")

    class Meta:
        model = FollowUp
        fields = ["type", "priority", "assignee", "reporter", "status"]

    def filter_overdue(self, queryset, name, value):
        from datetime import date
        today = date.today()
        if value:
            return queryset.filter(
                due_date__lt=today,
                workflow_state__is_final=False,
            )
        return queryset.exclude(
            due_date__lt=today,
            workflow_state__is_final=False,
        )
