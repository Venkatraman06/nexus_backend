import django_filters

from .models import Client, Project


class ClientFilter(django_filters.FilterSet):
    category = django_filters.UUIDFilter()
    contact_person = django_filters.CharFilter(lookup_expr="icontains")

    class Meta:
        model = Client
        fields = ["category"]


class ProjectFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    business_type = django_filters.UUIDFilter()
    billing_type = django_filters.UUIDFilter()
    client = django_filters.UUIDFilter()
    manager = django_filters.UUIDFilter()
    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")

    exclude_finished = django_filters.BooleanFilter(method="filter_exclude_finished")

    class Meta:
        model = Project
        fields = ["is_active", "business_type", "billing_type", "client", "manager", "exclude_finished"]

    def filter_exclude_finished(self, queryset, name, value):
        if value:
            return queryset.exclude(
                workflow_state__is_final=True
            ).exclude(
                workflow_state__slug__in=["completed", "finished", "closed", "cancelled", "done"]
            )
        return queryset
