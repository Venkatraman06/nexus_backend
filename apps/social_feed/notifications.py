"""Social feed notifications — notify admins/HR of pending posts and all employees of published posts."""

from __future__ import annotations

from apps.notifications.constants import EventType, ReferenceType
from apps.notifications.publisher import publish_event


def _active_admin_hr_ids():
    """Return IDs of users with pmt.social_feed.manage permission."""
    from apps.accounts.models import Employee
    return list(
        Employee.objects.filter(
            is_active=True, is_deleted=False,
        ).exclude(
            keycloak_group__isnull=True,
        ).values_list("id", flat=True)[:200]
    )


def publish_social_post_pending_approval(post, *, actor_id: str | None = None) -> None:
    """Notify admin/HR users when a post is submitted for approval."""
    content_preview = (post.content or "")[:120]
    if len(post.content or "") > 120:
        content_preview += "…"

    publish_event(
        EventType.SOCIAL_POST_PENDING_APPROVAL,
        ReferenceType.SOCIAL_POST,
        str(post.id),
        payload={
            "title": post.title,
            "content_preview": content_preview,
            "created_by_name": post.created_by_name or (
                post.created_by.full_name if post.created_by else "Unknown"
            ),
            "created_by_id": str(post.created_by_id) if post.created_by_id else "",
        },
        actor_id=actor_id,
        recipient_ids=_active_admin_hr_ids(),
        dedup_key=f"social_post.pending_approval:{post.id}",
    )


def publish_social_post_published(post, *, actor_id: str | None = None) -> None:
    """Notify all active employees when a company-wide post is published."""
    from apps.accounts.models import Employee

    if not post.is_company_wide:
        return

    all_employees = list(
        Employee.objects.filter(
            is_active=True, is_deleted=False,
        ).values_list("id", flat=True)[:500]
    )

    content_preview = (post.content or "")[:120]
    if len(post.content or "") > 120:
        content_preview += "…"

    publish_event(
        EventType.SOCIAL_POST_PUBLISHED,
        ReferenceType.SOCIAL_POST,
        str(post.id),
        payload={
            "title": post.title,
            "content_preview": content_preview,
            "created_by_name": post.created_by_name or (
                post.created_by.full_name if post.created_by else "Unknown"
            ),
            "created_by_id": str(post.created_by_id) if post.created_by_id else "",
        },
        actor_id=actor_id,
        recipient_ids=[str(eid) for eid in all_employees],
        dedup_key=f"social_post.published:{post.id}",
    )
