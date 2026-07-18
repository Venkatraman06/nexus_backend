from django.db import models

from packages.workflow.models import State
from packages.workflow.services import ProceedingService, StateService, TransitionService


class StateField(models.ForeignKey):
    """
    Drop-in ForeignKey that adds workflow methods to the host model.
    Usage:
        class WorkItem(BaseModel):
            workflow_state = StateField(related_name="workitem_states")
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("to", "pmt_workflow.State")
        kwargs.setdefault("null", True)
        kwargs.setdefault("blank", True)
        kwargs.setdefault("on_delete", models.SET_NULL)
        super().__init__(*args, **kwargs)

    def contribute_to_class(self, cls, name, **kwargs):
        field_name = name

        @property
        def state_history(self_inner):
            return ProceedingService.get_history(self_inner)

        def proceed(self_inner, user, destination_slug, comments=""):
            self_inner._state_field_name = field_name
            return TransitionService.proceed(self_inner, user, destination_slug, comments)

        def get_state(self_inner):
            return getattr(self_inner, field_name)

        def set_state(self_inner, state):
            setattr(self_inner, field_name, state)

        def get_available_next_states(self_inner):
            return StateService.get_available_next_states(self_inner)

        _add = cls.add_to_class
        if not hasattr(cls, "proceed"):
            _add("proceed", proceed)
        if not hasattr(cls, "get_state"):
            _add("get_state", get_state)
        if not hasattr(cls, "set_state"):
            _add("set_state", set_state)
        if not hasattr(cls, "state_history"):
            _add("state_history", state_history)
        if not hasattr(cls, "get_available_next_states"):
            _add("get_available_next_states", get_available_next_states)

        super().contribute_to_class(cls, name, **kwargs)
