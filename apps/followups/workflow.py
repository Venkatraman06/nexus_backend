"""Follow-up workflow seeding and transition helpers."""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from packages.workflow.exceptions import WorkflowTransitionError
from packages.workflow.models import Proceeding, State, Transition

FOLLOWUP_STATES = [
    {"name": "Planning",    "slug": "planning",   "color_code": "#14B8A6", "order": 1, "is_initial": True,  "is_final": False},
    {"name": "In Progress", "slug": "inprogress", "color_code": "#3B82F6", "order": 2, "is_initial": False, "is_final": False},
    {"name": "Completed",   "slug": "completed",  "color_code": "#10B981", "order": 3, "is_initial": False, "is_final": True},
    {"name": "Cancelled",   "slug": "cancelled",  "color_code": "#EF4444", "order": 4, "is_initial": False, "is_final": True},
]

FOLLOWUP_TRANSITIONS = [
    ("planning",   "inprogress", "Start"),
    ("planning",   "completed",  "Mark Done"),
    ("inprogress", "completed",  "Mark Done"),
    ("inprogress", "planning",   "Back"),
    ("completed",  "cancelled",  "Cancel"),
    ("cancelled",  "planning",   "Reopen"),
]


def _followup_content_type():
    from apps.followups.models import FollowUp
    return ContentType.objects.get_for_model(FollowUp)


@transaction.atomic
def ensure_followup_workflow() -> None:
    """Create follow-up states/transitions if missing (safe to call repeatedly)."""
    ct = _followup_content_type()
    state_map: dict[str, State] = {}

    for cfg in FOLLOWUP_STATES:
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

    for src_slug, dst_slug, label in FOLLOWUP_TRANSITIONS:
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


def assign_initial_state(followup) -> None:
    ct = _followup_content_type()
    if followup.workflow_state_id:
        canonical = _canonical_state(ct, followup.workflow_state)
        if canonical and canonical.id != followup.workflow_state_id:
            followup.workflow_state = canonical
            followup.save(update_fields=["workflow_state"])
        return

    initial = State.objects.filter(content_type=ct, is_initial=True).order_by("order").first()
    if initial:
        followup.workflow_state = initial
        followup.save(update_fields=["workflow_state"])


def get_allowed_destination_slugs(followup, user=None) -> list[str]:
    ensure_followup_workflow()
    assign_initial_state(followup)

    ct = _followup_content_type()
    current = _canonical_state(ct, followup.workflow_state)
    if not current:
        return []

    transitions = Transition.objects.filter(
        content_type=ct,
        source_state__slug=current.slug,
    ).select_related("destination_state")
    return [t.destination_state.slug for t in transitions if t.destination_state]


@transaction.atomic
def proceed_followup(followup, user, destination_slug: str, comments: str = "") -> Proceeding | None:
    ensure_followup_workflow()
    assign_initial_state(followup)

    ct = _followup_content_type()
    current = _canonical_state(ct, followup.workflow_state)
    if current is None:
        raise WorkflowTransitionError("Follow-up has no workflow state.")

    if current.content_type_id != ct.id:
        followup.workflow_state = current
        followup.save(update_fields=["workflow_state"])

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

    followup.workflow_state = destination
    followup.save(update_fields=["workflow_state"])

    return Proceeding.objects.create(
        content_type=ct,
        object_id=followup.pk,
        transition=transition,
        previous_state=current,
        state=destination,
        comments=comments,
        transitioned_by=user,
    )
