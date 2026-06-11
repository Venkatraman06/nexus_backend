import django_filters

from .models import Document


class DocumentFilter(django_filters.FilterSet):
    document_type = django_filters.CharFilter()
    status        = django_filters.CharFilter()
    client        = django_filters.UUIDFilter()
    project       = django_filters.UUIDFilter()
    division      = django_filters.UUIDFilter()
    currency      = django_filters.CharFilter()

    created_from  = django_filters.DateFilter(field_name="created_at", lookup_expr="date__gte")
    created_to    = django_filters.DateFilter(field_name="created_at", lookup_expr="date__lte")
    valid_from    = django_filters.DateFilter(field_name="valid_until", lookup_expr="gte")
    valid_to      = django_filters.DateFilter(field_name="valid_until", lookup_expr="lte")

    class Meta:
        model  = Document
        fields = ["document_type", "status", "client", "project", "division", "currency"]
