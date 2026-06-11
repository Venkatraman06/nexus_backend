"""
Public API for domain modules — publish events, never create Notification rows directly.
"""

from __future__ import annotations

import logging

from apps.notifications.engine import NotificationEngine
from apps.notifications.events import DomainEvent

logger = logging.getLogger(__name__)


def publish_event(
    event_type: str,
    reference_type: str,
    reference_id: str,
    payload: dict | None = None,
    *,
    actor_id: str | None = None,
    recipient_ids: list[str] | None = None,
    dedup_key: str | None = None,
    action_url: str | None = None,
    async_delivery: bool = False,
) -> None:
    """
    Publish a domain event to the notification engine.

    Modules should only call this function — never import Notification model directly.
    Set async_delivery=True to enqueue via Celery (non-blocking).
    """
    event = DomainEvent(
        event_type=event_type,
        reference_type=reference_type,
        reference_id=str(reference_id),
        payload=payload or {},
        actor_id=actor_id,
        recipient_ids=recipient_ids,
        dedup_key=dedup_key,
        action_url=action_url,
    )

    if async_delivery:
        try:
            from apps.notifications.tasks import process_domain_event_task
            process_domain_event_task.delay(_event_to_dict(event))
            return
        except Exception as exc:
            logger.warning(
                "Async notification delivery unavailable (%s), processing synchronously",
                exc,
            )

    try:
        NotificationEngine.process(event)
    except Exception as exc:
        logger.exception("Notification publish failed for %s: %s", event_type, exc)


def _event_to_dict(event: DomainEvent) -> dict:
    return {
        "event_type": event.event_type,
        "reference_type": event.reference_type,
        "reference_id": event.reference_id,
        "payload": event.payload,
        "actor_id": event.actor_id,
        "recipient_ids": event.recipient_ids,
        "dedup_key": event.dedup_key,
        "action_url": event.action_url,
    }


def _dict_to_event(data: dict) -> DomainEvent:
    return DomainEvent(**data)
