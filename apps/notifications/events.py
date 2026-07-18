"""Domain event payload passed by modules — notifications app owns delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID


@dataclass
class DomainEvent:
    event_type: str
    reference_type: str
    reference_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    actor_id: str | None = None
    recipient_ids: list[str] | None = None
    dedup_key: str | None = None
    action_url: str | None = None

    def __post_init__(self):
        if isinstance(self.reference_id, UUID):
            self.reference_id = str(self.reference_id)
        if self.actor_id and isinstance(self.actor_id, UUID):
            self.actor_id = str(self.actor_id)
