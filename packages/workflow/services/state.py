from django.contrib.contenttypes.models import ContentType

from packages.workflow.models import State, Transition


class StateService:
    @staticmethod
    def get_initial_state(model_class) -> State | None:
        ct = ContentType.objects.get_for_model(model_class)
        return State.objects.filter(content_type=ct, is_initial=True).first()

    @staticmethod
    def get_available_next_states(workflow_object, user=None) -> list[State]:
        from packages.workflow.services.transition import TransitionService
        transitions = TransitionService.get_allowed_transitions(workflow_object, user)
        return [t.destination_state for t in transitions if t.destination_state]
