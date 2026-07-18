import django_filters

from .models import WorkLog


class WorkLogFilter(django_filters.FilterSet):
    employee = django_filters.UUIDFilter()
    ticket = django_filters.UUIDFilter()
    project = django_filters.UUIDFilter(field_name="ticket__project")
    log_date_from = django_filters.DateFilter(field_name="log_date", lookup_expr="gte")
    log_date_to = django_filters.DateFilter(field_name="log_date", lookup_expr="lte")
    is_billable = django_filters.BooleanFilter()

    class Meta:
        model = WorkLog
        fields = ["employee", "ticket", "is_billable"]
