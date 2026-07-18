"""Todo workflow seeding and transition helpers."""

from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from packages.workflow.exceptions import WorkflowTransitionError
from packages.workflow.models import Proceeding, State, Transition

TODO_STATES = [
    {"name": "Open",        "slug": "open",        "color_code": "#6366F1", "order": 1, "is_initial": True,  "is_final": False},
    {"name": "In Progress", "slug": "inprogress",  "color_code": "#1677ff", "order": 2, "is_initial": False, "is_final": False},
    {"name": "Done",        "slug": "done",        "color_code": "#10B981", "order": 3, "is_initial": False, "is_final": True},
    {"name": "Cancelled",   "slug": "cancelled",   "color_code": "#94A3B8", "order": 4, "is_initial": False, "is_final": True},
]

TODO_TRANSITIONS = [
    ("open",       "inprogress", "Start"),
    ("open",       "done",       "Mark Done"),
    ("inprogress", "done",       "Mark Done"),
    ("inprogress", "open",       "Back"),
    ("done",       "cancelled",  "Cancel"),
    ("cancelled",  "open",       "Reopen"),
]


def _todo_content_type():
    from apps.todos.models import Todo
    return ContentType.objects.get_for_model(Todo)


def _canonical_state(ct, state: State | None) -> State | None:
    if state is None:
        return None
    if state.content_type_id == ct.id:
        return state
    return State.objects.filter(content_type=ct, slug=state.slug).first()


@transaction.atomic
def ensure_todo_workflow() -> None:
    ct = _todo_content_type()
    state_map: dict[str, State] = {}

    for cfg in TODO_STATES:
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

    for src_slug, dst_slug, label in TODO_TRANSITIONS:
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


def assign_initial_state(todo) -> None:
    ct = _todo_content_type()
    if todo.workflow_state_id:
        canonical = _canonical_state(ct, todo.workflow_state)
        if canonical and canonical.id != todo.workflow_state_id:
            todo.workflow_state = canonical
            todo.save(update_fields=["workflow_state"])
        return

    initial = State.objects.filter(content_type=ct, is_initial=True).order_by("order").first()
    if initial:
        todo.workflow_state = initial
        todo.save(update_fields=["workflow_state"])


def get_allowed_destination_slugs(todo, user=None) -> list[str]:
    ensure_todo_workflow()
    assign_initial_state(todo)

    ct = _todo_content_type()
    current = _canonical_state(ct, todo.workflow_state)
    if not current:
        return []

    transitions = Transition.objects.filter(
        content_type=ct,
        source_state__slug=current.slug,
    ).select_related("destination_state")
    return [t.destination_state.slug for t in transitions if t.destination_state]


@transaction.atomic
def proceed_todo(todo, user, destination_slug: str, comments: str = "") -> Proceeding | None:
    ensure_todo_workflow()
    assign_initial_state(todo)

    ct = _todo_content_type()
    current = _canonical_state(ct, todo.workflow_state)
    if current is None:
        raise WorkflowTransitionError("Todo has no workflow state.")

    if current.content_type_id != ct.id:
        todo.workflow_state = current
        todo.save(update_fields=["workflow_state"])

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

    todo.workflow_state = destination
    todo.save(update_fields=["workflow_state"])

    return Proceeding.objects.create(
        content_type=ct,
        object_id=todo.pk,
        transition=transition,
        previous_state=current,
        state=destination,
        comments=comments,
        transitioned_by=user,
    )
