import django_filters

from .models import Client, Project


class ProjectFilter(django_filters.FilterSet):
    is_active = django_filters.BooleanFilter()
    business_type = django_filters.UUIDFilter()
    billing_type = django_filters.UUIDFilter()
    client = django_filters.UUIDFilter()
    manager = django_filters.UUIDFilter()
    start_date_from = django_filters.DateFilter(field_name="start_date", lookup_expr="gte")
    start_date_to = django_filters.DateFilter(field_name="start_date", lookup_expr="lte")

    class Meta:
        model = Project
        fields = ["is_active", "business_type", "billing_type", "client", "manager"]
