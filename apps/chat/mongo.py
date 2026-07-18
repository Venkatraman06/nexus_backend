"""
Message storage — MongoDB, not Postgres. Everything that used to be five
separate Postgres child tables (attachments, mentions, reactions, stars,
delivery receipts) is embedded directly on the message document; that's
the idiomatic Mongo shape and matches the original spec's own rationale for
splitting high-volume/flexible-schema chat data out of the relational store.

Conversation / ConversationParticipant / ConversationAuditLog stay in
Postgres (apps/chat/models.py) — relational membership data, unchanged.

Search: substring `$regex` match on `body` (and attachment filenames),
not Mongo's `$text` operator. `$text` needs a text index with server-side
language stemming that mongomock (used in tests) doesn't implement, and a
regex scan is more than adequate at this app's scale — same trade-off this
codebase already made choosing Postgres ILIKE filtering over full linguistic
search elsewhere.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone as dt_timezone

import pymongo
from django.conf import settings

_client = None
_indexes_ready = False


import urllib.parse

def _build_client():
    if settings.MONGO_USER:
        auth_db = settings.MONGO_NAME or "admin"
        user = urllib.parse.quote_plus(settings.MONGO_USER)
        passwd = urllib.parse.quote_plus(settings.MONGO_PASSWORD)
        uri = (
            f"mongodb://{user}:{passwd}"
            f"@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"
            f"?authSource={auth_db}"
        )
    else:
        uri = f"mongodb://{settings.MONGO_HOST}:{settings.MONGO_PORT}/"
    return pymongo.MongoClient(uri)


def get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def set_client(client) -> None:
    """Test hook — inject a mongomock.MongoClient() instead of connecting for real."""
    global _client, _indexes_ready
    _client = client
    _indexes_ready = False


def get_db():
    return get_client()[settings.MONGO_NAME]


def get_messages_collection():
    global _indexes_ready
    collection = get_db()["messages"]
    if not _indexes_ready:
        collection.create_index([("conversation_id", 1), ("created_at", 1)])
        collection.create_index([("mentions", 1)])
        collection.create_index([("stars", 1)])
        _indexes_ready = True
    return collection


def _now():
    return datetime.now(dt_timezone.utc)


def new_id() -> str:
    return str(uuid.uuid4())


# ── writes ──────────────────────────────────────────────────────────────

def create_message(
    conversation_id: str, sender_id: str, body: str, *,
    reply_to: str | None = None, is_important: bool = False,
    mentions: list[str] | None = None, attachments: list[dict] | None = None,
) -> dict:
    now = _now()
    doc = {
        "_id": new_id(),
        "conversation_id": str(conversation_id),
        "sender_id": str(sender_id),
        "body": body,
        "reply_to": reply_to,
        "is_edited": False,
        "edited_at": None,
        "is_important": is_important,
        "is_deleted": False,
        "mentions": [str(m) for m in (mentions or [])],
        "attachments": attachments or [],
        "reactions": [],
        "stars": [],
        "delivery": [],
        "created_at": now,
        "updated_at": now,
        "created_by": str(sender_id),
        "updated_by": str(sender_id),
    }
    get_messages_collection().insert_one(doc)
    return doc


def get_message(message_id: str) -> dict | None:
    return get_messages_collection().find_one({"_id": str(message_id)})


def list_messages(conversation_id: str, *, is_important: bool | None = None) -> list[dict]:
    query: dict = {"conversation_id": str(conversation_id)}
    if is_important is not None:
        query["is_important"] = is_important
    return list(get_messages_collection().find(query).sort("created_at", pymongo.ASCENDING))


def update_message_body(message_id: str, body: str, updated_by: str) -> dict | None:
    now = _now()
    get_messages_collection().update_one(
        {"_id": str(message_id)},
        {"$set": {
            "body": body, "is_edited": True, "edited_at": now,
            "updated_at": now, "updated_by": str(updated_by),
        }},
    )
    return get_message(message_id)


def soft_delete_message(message_id: str, updated_by: str) -> dict | None:
    now = _now()
    get_messages_collection().update_one(
        {"_id": str(message_id)},
        {"$set": {"is_deleted": True, "updated_at": now, "updated_by": str(updated_by)}},
    )
    return get_message(message_id)


def toggle_important(message_id: str, updated_by: str) -> dict | None:
    message = get_message(message_id)
    if message is None:
        return None
    new_value = not message.get("is_important", False)
    get_messages_collection().update_one(
        {"_id": str(message_id)},
        {"$set": {"is_important": new_value, "updated_by": str(updated_by), "updated_at": _now()}},
    )
    return get_message(message_id)


def toggle_star(message_id: str, employee_id: str) -> bool:
    """Returns the new starred state for this employee."""
    employee_id = str(employee_id)
    message = get_message(message_id)
    if message is None:
        return False
    if employee_id in message.get("stars", []):
        get_messages_collection().update_one({"_id": str(message_id)}, {"$pull": {"stars": employee_id}})
        return False
    get_messages_collection().update_one({"_id": str(message_id)}, {"$addToSet": {"stars": employee_id}})
    return True


def update_attachment_scan_status(message_id: str, attachment_id: str, status: str, scanned_at) -> None:
    get_messages_collection().update_one(
        {"_id": str(message_id), "attachments.id": str(attachment_id)},
        {"$set": {
            "attachments.$.scan_status": status,
            "attachments.$.scanned_at": scanned_at,
        }},
    )


# ── reads for filtered views ────────────────────────────────────────────

def mentions_for(employee_id: str, conversation_ids: list[str]) -> list[dict]:
    return list(
        get_messages_collection()
        .find({
            "mentions": str(employee_id),
            "conversation_id": {"$in": [str(c) for c in conversation_ids]},
            "is_deleted": False,
        })
        .sort("created_at", pymongo.DESCENDING)
    )


def starred_for(employee_id: str, conversation_ids: list[str]) -> list[dict]:
    return list(
        get_messages_collection()
        .find({
            "stars": str(employee_id),
            "conversation_id": {"$in": [str(c) for c in conversation_ids]},
            "is_deleted": False,
        })
        .sort("created_at", pymongo.DESCENDING)
    )


def search_messages(query: str, conversation_ids: list[str], conversation_id: str | None = None) -> dict:
    scope = {"conversation_id": str(conversation_id)} if conversation_id else {
        "conversation_id": {"$in": [str(c) for c in conversation_ids]},
    }
    base = {**scope, "is_deleted": False}

    messages = list(
        get_messages_collection()
        .find({**base, "body": {"$regex": query, "$options": "i"}})
        .sort("created_at", pymongo.DESCENDING)
        .limit(50)
    )
    files = list(
        get_messages_collection()
        .find({**base, "attachments.original_filename": {"$regex": query, "$options": "i"}})
        .sort("created_at", pymongo.DESCENDING)
        .limit(50)
    )
    return {"messages": messages, "files": files}


def last_message_for(conversation_id: str) -> dict | None:
    cursor = (
        get_messages_collection()
        .find({"conversation_id": str(conversation_id), "is_deleted": False})
        .sort("created_at", pymongo.DESCENDING)
        .limit(1)
    )
    return next(cursor, None)


def unread_count(conversation_id: str, since, exclude_employee_id: str) -> int:
    query = {
        "conversation_id": str(conversation_id),
        "is_deleted": False,
        "sender_id": {"$ne": str(exclude_employee_id)},
    }
    if since is not None:
        query["created_at"] = {"$gt": since}
    return get_messages_collection().count_documents(query)
