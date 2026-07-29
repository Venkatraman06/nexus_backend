import django_filters

from .models import Ticket


class TicketFilter(django_filters.FilterSet):
    project = django_filters.UUIDFilter()
    type = django_filters.CharFilter(lookup_expr="exact")
    priority = django_filters.CharFilter(lookup_expr="exact")
    assignee = django_filters.UUIDFilter()
    reporter = django_filters.UUIDFilter()
    approved = django_filters.BooleanFilter()
    parent = django_filters.UUIDFilter()
    due_date_from = django_filters.DateFilter(field_name="due_date", lookup_expr="gte")
    due_date_to = django_filters.DateFilter(field_name="due_date", lookup_expr="lte")

    exclude_finished = django_filters.BooleanFilter(method="filter_exclude_finished")

    class Meta:
        model = Ticket
        fields = ["project", "type", "priority", "assignee", "reporter", "approved", "parent", "exclude_finished"]

    def filter_exclude_finished(self, queryset, name, value):
        if value:
            return queryset.exclude(
                workflow_state__is_final=True
            ).exclude(
                workflow_state__slug__in=["closed", "cancelled", "canceled", "completed", "finished", "done"]
            ).exclude(
                project__workflow_state__is_final=True
            ).exclude(
                project__workflow_state__slug__in=["completed", "finished", "closed", "cancelled", "done"]
            )
        return queryset
