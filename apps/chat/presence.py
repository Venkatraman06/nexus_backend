"""
Online presence, tracked in Redis (not the DB — it's inherently ephemeral).
Shared by the WebSocket consumer (writer) and REST/task code (reader, to
decide whether a message needs a push notification).
"""
from django.core.cache import cache

PRESENCE_TTL = 60


def presence_key(employee_id) -> str:
    return f"chat:presence:{employee_id}"


def is_online(employee_id) -> bool:
    return cache.get(presence_key(employee_id)) is not None


def touch_presence(employee_id) -> None:
    cache.set(presence_key(employee_id), True, timeout=PRESENCE_TTL)


def clear_presence(employee_id) -> None:
    cache.delete(presence_key(employee_id))
