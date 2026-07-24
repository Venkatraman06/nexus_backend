import django_filters

from .models import SocialPost


class SocialPostFilter(django_filters.FilterSet):
    status = django_filters.CharFilter(field_name="workflow_state__slug")
    created_by = django_filters.UUIDFilter(field_name="created_by_id")
    search = django_filters.CharFilter(method="filter_search")

    class Meta:
        model = SocialPost
        fields = ["status", "created_by"]

    def filter_search(self, queryset, name, value):
        from django.db.models import Q
        return queryset.filter(
            Q(title__icontains=value) | Q(content__icontains=value)
        )
