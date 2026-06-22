"""Project workflow constants — configurable via Django settings."""

from django.conf import settings

DEFAULT_PROJECT_DUE_EXCLUDED_WORKFLOW_SLUGS = ("close", "cancelled")
DEFAULT_ACTIVE_BUSINESS_WORKFLOW_SLUGS = ("kickoff", "ongoing")


def get_project_due_excluded_workflow_slugs() -> tuple[str, ...]:
    """
    Slugs excluded from due / overdue / delayed tracking on dashboards.
    Override in settings: PROJECT_DUE_EXCLUDED_WORKFLOW_SLUGS = ["close", "cancelled", ...]
    """
    configured = getattr(settings, "PROJECT_DUE_EXCLUDED_WORKFLOW_SLUGS", None)
    if configured is None:
        return DEFAULT_PROJECT_DUE_EXCLUDED_WORKFLOW_SLUGS
    return tuple(configured)


def get_active_business_workflow_slugs() -> tuple[str, ...]:
    """
    Workflow slugs that count as an active (in-business) project on dashboards.
    Override in settings: ACTIVE_BUSINESS_WORKFLOW_SLUGS = ["kickoff", "ongoing", ...]
    """
    configured = getattr(settings, "ACTIVE_BUSINESS_WORKFLOW_SLUGS", None)
    if configured is None:
        return DEFAULT_ACTIVE_BUSINESS_WORKFLOW_SLUGS
    return tuple(configured)


def project_excluded_from_due_tracking(project) -> bool:
    """True when a project must not count as due, overdue, or delayed."""
    state = getattr(project, "workflow_state", None)
    if not state:
        return False
    slug = getattr(state, "slug", None) or ""
    if slug in get_project_due_excluded_workflow_slugs():
        return True
    return bool(getattr(state, "is_final", False))
