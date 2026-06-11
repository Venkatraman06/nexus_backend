from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from packages.workflow.models import Proceeding, State, Transition
from packages.workflow.exceptions import WorkflowTransitionError

# Models where transition group rules are skipped — permission is enforced at the API layer.
_GROUP_CHECK_BYPASS = {
    ("followups", "followup"),
}


def _bypasses_group_check(workflow_object) -> bool:
    ct = ContentType.objects.get_for_model(workflow_object)
    return (ct.app_label, ct.model) in _GROUP_CHECK_BYPASS


class TransitionService:
    @staticmethod
    def get_allowed_transitions(workflow_object, user=None):
        """
        Returns transitions from the current state that the given user can execute.
        - Staff / PMO users bypass group checks.
        - If a transition has no groups, anyone can execute it.
        - Otherwise the user must be a member of at least one allowed group.
        """
        ct = ContentType.objects.get_for_model(workflow_object)
        current_state = workflow_object.get_state()
        qs = (
            Transition.objects.filter(content_type=ct, source_state=current_state)
            .select_related("destination_state")
            .prefetch_related("groups")
        )

        if user is None:
            return list(qs)

        if _bypasses_group_check(workflow_object):
            return list(qs)

        if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
            return list(qs)

        allowed = []
        user_group_ids = set()
        if hasattr(user, "workflow_groups"):
            user_group_ids = set(user.workflow_groups.values_list("id", flat=True))
        user_kc_group = (getattr(user, "keycloak_group", None) or "").strip()

        for t in qs:
            transition_groups = list(t.groups.all())
            if not transition_groups:
                allowed.append(t)
                continue
            transition_group_ids = {g.id for g in transition_groups}
            transition_group_names = {g.name for g in transition_groups}
            if transition_group_ids & user_group_ids:
                allowed.append(t)
            elif user_kc_group and user_kc_group in transition_group_names:
                allowed.append(t)
        return allowed

    @staticmethod
    @transaction.atomic
    def proceed(workflow_object, user, destination_state_slug: str, comments: str = "") -> Proceeding:
        ct = ContentType.objects.get_for_model(workflow_object)
        current_state = workflow_object.get_state()

        destination_state = State.objects.filter(
            content_type=ct, slug=destination_state_slug
        ).first()
        if destination_state is None:
            raise WorkflowTransitionError(f"State '{destination_state_slug}' not found.")

        allowed = TransitionService.get_allowed_transitions(workflow_object, user)
        valid_transition = next(
            (t for t in allowed if t.destination_state_id == destination_state.pk),
            None,
        )
        if valid_transition is None:
            raise WorkflowTransitionError(
                f"No valid transition from '{current_state}' to '{destination_state}'."
            )

        workflow_object.set_state(destination_state)
        workflow_object.save(update_fields=[workflow_object._state_field_name])

        return Proceeding.objects.create(
            content_type=ct,
            object_id=workflow_object.pk,
            transition=valid_transition,
            previous_state=current_state,
            state=destination_state,
            comments=comments,
            transitioned_by=user,
        )
