from django.db.models import Q, QuerySet

from .constants import (
    get_active_business_workflow_slugs,
    get_project_due_excluded_workflow_slugs,
)


class ProjectQuerySet(QuerySet):
    """Project queryset helpers."""

    def in_active_business(self) -> "ProjectQuerySet":
        """Projects currently in business (kickoff / ongoing by default)."""
        slugs = get_active_business_workflow_slugs()
        if not slugs:
            return self.none()
        return self.filter(workflow_state__slug__in=slugs)

    def eligible_for_due_tracking(self) -> "ProjectQuerySet":
        """
        Active delivery projects only — excludes closed/cancelled (configurable slugs)
        and any workflow state marked final.
        """
        slugs = get_project_due_excluded_workflow_slugs()
        qs = self
        if slugs:
            qs = qs.exclude(workflow_state__slug__in=slugs)
        return qs.filter(
            Q(workflow_state__isnull=True) | Q(workflow_state__is_final=False),
        )
