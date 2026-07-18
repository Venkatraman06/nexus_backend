"""Social post approval workflow — draft → approval → published."""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from packages.workflow.exceptions import WorkflowTransitionError
from packages.workflow.models import Proceeding, State, Transition

SOCIAL_POST_STATES = [
    {"name": "Draft",            "slug": "draft",            "color_code": "#6B7280", "order": 1, "is_initial": True,  "is_final": False},
    {"name": "Pending Approval", "slug": "pending_approval", "color_code": "#F59E0B", "order": 2, "is_initial": False, "is_final": False},
    {"name": "Approved",         "slug": "approved",         "color_code": "#10B981", "order": 3, "is_initial": False, "is_final": False},
    {"name": "Rejected",         "slug": "rejected",         "color_code": "#EF4444", "order": 4, "is_initial": False, "is_final": False},
    {"name": "Published",        "slug": "published",        "color_code": "#3B82F6", "order": 5, "is_initial": False, "is_final": True},
]

SOCIAL_POST_TRANSITIONS = [
    # Creator transitions
    ("draft",            "pending_approval", "Submit for Approval"),
    ("rejected",         "draft",            "Revise & Resubmit"),
    # Admin/HR transitions
    ("draft",            "published",        "Publish Directly"),
    ("pending_approval", "approved",         "Approve"),
    ("pending_approval", "rejected",         "Reject"),
    ("pending_approval", "published",        "Approve & Publish"),
    ("approved",         "published",        "Publish"),
    ("published",        "draft",            "Unpublish"),
]


def _social_post_content_type():
    from apps.social_feed.models import SocialPost
    return ContentType.objects.get_for_model(SocialPost)


@transaction.atomic
def ensure_social_post_workflow() -> None:
    """Create social post states/transitions if missing (safe to call repeatedly)."""
    ct = _social_post_content_type()
    state_map: dict[str, State] = {}

    for cfg in SOCIAL_POST_STATES:
        obj, _ = State.objects.get_or_create(
            content_type=ct,
            slug=cfg["slug"],
            defaults={
                "name": cfg["name"],
                "color_code": cfg["color_code"],
                "order": cfg["order"],
                "is_initial": cfg["is_initial"],
                "is_final": cfg["is_final"],
                "label": cfg["name"],
            },
        )
        state_map[cfg["slug"]] = obj

    for src_slug, dst_slug, label in SOCIAL_POST_TRANSITIONS:
        src = state_map.get(src_slug)
        dst = state_map.get(dst_slug)
        if not src or not dst:
            continue
        transition, created = Transition.objects.get_or_create(
            content_type=ct,
            source_state=src,
            destination_state=dst,
            defaults={"label": label},
        )
        if not created and not transition.label:
            transition.label = label
            transition.save(update_fields=["label"])


def _canonical_state(ct, state: State | None) -> State | None:
    if state is None:
        return None
    if state.content_type_id == ct.id:
        return state
    return State.objects.filter(content_type=ct, slug=state.slug).first()


def assign_initial_state(post) -> None:
    ct = _social_post_content_type()
    if post.workflow_state_id:
        canonical = _canonical_state(ct, post.workflow_state)
        if canonical and canonical.id != post.workflow_state_id:
            post.workflow_state = canonical
            post.save(update_fields=["workflow_state"])
        return

    initial = State.objects.filter(content_type=ct, is_initial=True).order_by("order").first()
    if initial:
        post.workflow_state = initial
        post.save(update_fields=["workflow_state"])


def _user_can_manage(user, permissions=None) -> bool:
    if not user or not user.is_authenticated:
        return False
    if getattr(user, "is_superuser", False) or getattr(user, "is_staff", False):
        return True
    perms = permissions or getattr(user, "_permissions_cache", [])
    return "pmt.social_feed.manage" in perms


def get_allowed_destination_slugs(post, user=None, permissions=None) -> list[str]:
    ensure_social_post_workflow()
    assign_initial_state(post)

    ct = _social_post_content_type()
    current = _canonical_state(ct, post.workflow_state)
    if not current:
        return []

    is_owner = user and user.is_authenticated and post.created_by_id == user.pk
    is_admin = _user_can_manage(user, permissions)

    transitions = Transition.objects.filter(
        content_type=ct,
        source_state__slug=current.slug,
    ).select_related("destination_state")

    allowed = []
    for t in transitions:
        dest = t.destination_state
        if not dest:
            continue
        ds = dest.slug

        # Only admin/managers can: publish_directly, approve, reject, publish, approve_and_publish
        if ds in ("published", "approved", "rejected"):
            if not is_admin:
                continue

        # Only creator can: revise (from rejected → draft)
        if ds == "draft" and current.slug == "rejected":
            if not is_owner:
                continue

        # Submit for approval
        if ds == "pending_approval":
            if not is_owner:
                continue

        allowed.append(ds)

    return allowed


@transaction.atomic
def proceed_social_post(post, user, destination_slug: str, comments: str = "") -> Proceeding | None:
    ensure_social_post_workflow()
    assign_initial_state(post)

    ct = _social_post_content_type()
    current = _canonical_state(ct, post.workflow_state)
    if current is None:
        raise WorkflowTransitionError("Post has no workflow state.")

    if current.content_type_id != ct.id:
        post.workflow_state = current
        post.save(update_fields=["workflow_state"])

    destination = State.objects.filter(content_type=ct, slug=destination_slug).first()
    if destination is None:
        raise WorkflowTransitionError(f"State '{destination_slug}' not found.")

    if current.pk == destination.pk:
        return None

    transition = Transition.objects.filter(
        content_type=ct,
        source_state__slug=current.slug,
        destination_state__slug=destination_slug,
    ).first()

    if transition is None:
        raise WorkflowTransitionError(
            f"No valid transition from '{current.name}' to '{destination.name}'."
        )

    post.workflow_state = destination
    post.save(update_fields=["workflow_state"])

    return Proceeding.objects.create(
        content_type=ct,
        object_id=post.pk,
        transition=transition,
        previous_state=current,
        state=destination,
        comments=comments,
        transitioned_by=user,
    )
