from django.db.models import Q, QuerySet

from .constants import (
    get_project_due_excluded_workflow_slugs,
)


class ProjectQuerySet(QuerySet):
    """Project queryset helpers."""

    def in_active_business(self) -> "ProjectQuerySet":
        """
        Projects currently in active business.
        A project is active if it has been moved out of its initial state (e.g. enquiry)
        and is not in a final state (like close or cancelled).
        """
        return self.filter(
            is_active=True,
            workflow_state__isnull=False
        ).exclude(
            workflow_state__is_initial=True
        ).exclude(
            workflow_state__is_final=True
        )

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
