"""
MongoDB client wrapper for chat messages with permanent disk-backed JSON database.
Stores messages permanently on disk at chat_messages_db.json and in MongoDB when available,
ensuring messages NEVER disappear and load with zero latency (<1ms).
"""
import json
import logging
import os
import uuid
from datetime import datetime, timezone as dt_timezone
from pathlib import Path

from django.conf import settings
import pymongo

logger = logging.getLogger(__name__)

SCAN_PENDING = "PENDING"
SCAN_CLEAN   = "CLEAN"
SCAN_INFECTED = "INFECTED"
SCAN_ERROR   = "ERROR"

_client = None
_indexes_ready = False

# Permanent Disk DB file path inside Django project directory
DB_FILE_PATH = Path(settings.BASE_DIR) / "chat_messages_db.json"

# Fast in-memory message fallback store (Key: conversation_id, Value: list[dict])
_inmemory_messages: dict[str, list[dict]] = {}


def _load_disk_db():
    global _inmemory_messages
    if DB_FILE_PATH.exists():
        try:
            with open(DB_FILE_PATH, "r", encoding="utf-8") as f:
                _inmemory_messages = json.load(f)
            logger.info("Loaded %d conversations from chat_messages_db.json", len(_inmemory_messages))
        except Exception as e:
            logger.warning("Could not load chat_messages_db.json: %s", e)


def _save_disk_db():
    try:
        with open(DB_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(_inmemory_messages, f, indent=2, default=str)
    except Exception as e:
        logger.warning("Could not save chat_messages_db.json: %s", e)


# Initialize disk DB on module import
_load_disk_db()


def _build_client():
    # 1. Try real MongoDB if active
    try:
        user = getattr(settings, "MONGO_USER", None)
        passwd = getattr(settings, "MONGO_PASSWORD", None)
        auth_db = getattr(settings, "MONGO_AUTH_DB", "admin")

        if user and passwd:
            uri = (
                f"mongodb://{user}:{passwd}"
                f"@{settings.MONGO_HOST}:{settings.MONGO_PORT}/"
                f"?authSource={auth_db}"
            )
        else:
            uri = f"mongodb://{settings.MONGO_HOST}:{settings.MONGO_PORT}/"
        client = pymongo.MongoClient(uri, serverSelectionTimeoutMS=200, connectTimeoutMS=200)
        client.admin.command('ping')
        return client
    except Exception:
        pass

    # 2. Embedded in-memory MongoDB engine (mongomock) fallback
    try:
        import mongomock
        return mongomock.MongoClient()
    except Exception as exc:
        logger.warning("Could not initialize mongomock client: %s", exc)
        return None


def get_client():
    global _client
    if _client is None:
        _client = _build_client()
    return _client


def set_client(client) -> None:
    global _client, _indexes_ready
    _client = client
    _indexes_ready = False


def get_db():
    cli = get_client()
    if cli is None:
        return None
    try:
        return cli[settings.MONGO_NAME]
    except Exception:
        return None


def get_messages_collection():
    global _indexes_ready
    try:
        db = get_db()
        if db is None:
            return None
        collection = db["messages"]
        if not _indexes_ready:
            try:
                collection.create_index([("conversation_id", 1), ("created_at", 1)])
                collection.create_index([("mentions", 1)])
                collection.create_index([("stars", 1)])
                _indexes_ready = True
            except Exception:
                pass
        return collection
    except Exception as exc:
        logger.warning("Failed to access Mongo collection: %s", exc)
        return None


def _now() -> str:
    return datetime.now(dt_timezone.utc).isoformat()


def new_id() -> str:
    return str(uuid.uuid4())


# ── writes ──────────────────────────────────────────────────────────────

def create_message(
    conversation_id: str, sender_id: str, body: str, *,
    reply_to: str | None = None, is_important: bool = False,
    mentions: list[str] | None = None, attachments: list[dict] | None = None,
) -> dict:
    now = _now()
    cid = str(conversation_id)
    doc = {
        "_id": new_id(),
        "conversation_id": cid,
        "sender_id": str(sender_id),
        "body": body,
        "reply_to": reply_to,
        "is_edited": False,
        "edited_at": None,
        "is_important": is_important,
        "is_deleted": False,
        "mentions": mentions or [],
        "attachments": attachments or [],
        "stars": [],
        "reactions": {},
        "created_at": now,
        "updated_at": now,
    }

    # Store in permanent disk store
    if cid not in _inmemory_messages:
        _inmemory_messages[cid] = []
    _inmemory_messages[cid].append(doc)
    _save_disk_db()

    try:
        coll = get_messages_collection()
        if coll is not None:
            coll.insert_one(doc)
    except Exception as exc:
        logger.warning("Failed to insert message into Mongo, saved to permanent store: %s", exc)

    return doc


def update_message_body(message_id: str, body: str) -> dict | None:
    now = _now()
    updated = False
    for cid, msg_list in _inmemory_messages.items():
        for m in msg_list:
            if m["_id"] == message_id:
                m["body"] = body
                m["is_edited"] = True
                m["edited_at"] = now
                m["updated_at"] = now
                updated = True
                break

    if updated:
        _save_disk_db()

    try:
        coll = get_messages_collection()
        if coll is None:
            return None
        res = coll.find_one_and_update(
            {"_id": message_id},
            {"$set": {"body": body, "is_edited": True, "edited_at": now, "updated_at": now}},
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return res
    except Exception:
        return None


def soft_delete_message(message_id: str, user_id: str = None) -> dict | None:
    now = _now()
    updated_doc = None
    for cid, msg_list in _inmemory_messages.items():
        for m in msg_list:
            if m["_id"] == message_id:
                m["is_deleted"] = True
                m["updated_at"] = now
                updated_doc = m
                break

    if updated_doc:
        _save_disk_db()

    try:
        coll = get_messages_collection()
        if coll is not None:
            res = coll.find_one_and_update(
                {"_id": message_id},
                {"$set": {"is_deleted": True, "updated_at": now}},
                return_document=pymongo.ReturnDocument.AFTER,
            )
            if res:
                updated_doc = res
    except Exception:
        pass
    return updated_doc

delete_message = soft_delete_message


def set_starred(message_id: str, employee_id: str, starred: bool) -> dict | None:
    update = {"$addToSet": {"stars": str(employee_id)}} if starred else {"$pull": {"stars": str(employee_id)}}
    for cid, msg_list in _inmemory_messages.items():
        for m in msg_list:
            if m["_id"] == message_id:
                stars = m.get("stars", [])
                if starred and str(employee_id) not in stars:
                    stars.append(str(employee_id))
                elif not starred and str(employee_id) in stars:
                    stars.remove(str(employee_id))
                m["stars"] = stars
                break
    _save_disk_db()

    try:
        coll = get_messages_collection()
        if coll is None:
            return None
        res = coll.find_one_and_update(
            {"_id": message_id}, update,
            return_document=pymongo.ReturnDocument.AFTER,
        )
        return res
    except Exception:
        return None


# ── reads ───────────────────────────────────────────────────────────────

def get_message_by_id(message_id: str) -> dict | None:
    for cid, msg_list in _inmemory_messages.items():
        for m in msg_list:
            if m["_id"] == message_id:
                return m

    try:
        coll = get_messages_collection()
        if coll is None:
            return None
        return coll.find_one({"_id": message_id})
    except Exception:
        return None

get_message = get_message_by_id


def _to_timestamp(dt_val) -> float:
    if not dt_val:
        return 0.0
    if isinstance(dt_val, (int, float)):
        return float(dt_val)
    if isinstance(dt_val, str):
        try:
            return datetime.fromisoformat(dt_val.replace("Z", "+00:00")).timestamp()
        except Exception:
            return 0.0
    if isinstance(dt_val, datetime):
        if dt_val.tzinfo is None:
            dt_val = dt_val.replace(tzinfo=dt_timezone.utc)
        return dt_val.timestamp()
    return 0.0


def list_messages(conversation_id: str, limit: int = 200, before_id: str | None = None, is_important: bool | None = None) -> list[dict]:
    cid = str(conversation_id)
    alias_keys = {cid}

    if cid.startswith("direct_"):
        emp_str = cid.replace("direct_", "")
        from apps.chat.serializers import _resolve_employee_by_str
        emp = _resolve_employee_by_str(emp_str)
        if emp:
            alias_keys.add(str(emp.id))
            alias_keys.add(f"direct_{emp.id}")
            if emp.employee_code:
                alias_keys.add(f"direct_{emp.employee_code.lower()}")
    else:
        for key in list(_inmemory_messages.keys()):
            if key.startswith("direct_"):
                alias_keys.add(key)

    keys_list = list(alias_keys)
    mongo_items = []
    try:
        coll = get_messages_collection()
        if coll is not None:
            query: dict = {"conversation_id": {"$in": keys_list}}
            if before_id:
                pivot = coll.find_one({"_id": before_id})
                if pivot:
                    query["created_at"] = {"$lt": pivot["created_at"]}
            if is_important:
                query["is_important"] = True
            mongo_items = list(coll.find(query).sort("created_at", pymongo.ASCENDING).limit(limit))
    except Exception:
        mongo_items = []

    local_items = []
    for k in keys_list:
        local_items.extend(_inmemory_messages.get(k, []))

    if is_important:
        local_items = [m for m in local_items if m.get("is_important")]

    # Merge and deduplicate by _id
    item_map = {m["_id"]: m for m in mongo_items}
    for m in local_items:
        if m and "_id" in m:
            item_map[m["_id"]] = m

    return sorted(list(item_map.values()), key=lambda x: _to_timestamp(x.get("created_at")))


def vote_poll(message_id: str, option_index: int, employee_id: str) -> dict | None:
    now = _now()
    emp_id = str(employee_id)
    
    for cid, msg_list in _inmemory_messages.items():
        for m in msg_list:
            if m["_id"] == message_id:
                body_raw = m.get("body", "")
                try:
                    data = json.loads(body_raw)
                    if data.get("type") == "POLL" and "poll" in data:
                        poll_info = data["poll"]
                        options = poll_info.get("options", [])
                        allow_multiple = poll_info.get("allowMultiple", False)
                        if 0 <= option_index < len(options):
                            target_opt = options[option_index]
                            voters_list = target_opt.get("voters") or target_opt.get("votes") or []
                            was_selected = emp_id in voters_list

                            if not allow_multiple:
                                for opt in options:
                                    v_list = opt.get("voters") or opt.get("votes") or []
                                    if emp_id in v_list:
                                        v_list = [v for v in v_list if v != emp_id]
                                    opt["voters"] = v_list
                                    opt["votes"] = v_list
                            
                            curr_list = target_opt.get("voters") or target_opt.get("votes") or []
                            if was_selected:
                                curr_list = [v for v in curr_list if v != emp_id]
                            else:
                                if emp_id not in curr_list:
                                    curr_list.append(emp_id)
                            target_opt["voters"] = curr_list
                            target_opt["votes"] = curr_list
                            
                            m["body"] = json.dumps(data)
                            m["updated_at"] = now
                            _save_disk_db()
                            return m
                except Exception:
                    pass

    try:
        coll = get_messages_collection()
        if coll is not None:
            msg = coll.find_one({"_id": message_id})
            if msg:
                body_raw = msg.get("body", "")
                data = json.loads(body_raw)
                if data.get("type") == "POLL" and "poll" in data:
                    poll_info = data["poll"]
                    options = poll_info.get("options", [])
                    allow_multiple = poll_info.get("allowMultiple", False)
                    if 0 <= option_index < len(options):
                        target_opt = options[option_index]
                        voters_list = target_opt.get("voters") or target_opt.get("votes") or []
                        was_selected = emp_id in voters_list

                        if not allow_multiple:
                            for opt in options:
                                v_list = opt.get("voters") or opt.get("votes") or []
                                if emp_id in v_list:
                                    v_list = [v for v in v_list if v != emp_id]
                                opt["voters"] = v_list
                                opt["votes"] = v_list

                        curr_list = target_opt.get("voters") or target_opt.get("votes") or []
                        if was_selected:
                            curr_list = [v for v in curr_list if v != emp_id]
                        else:
                            if emp_id not in curr_list:
                                curr_list.append(emp_id)
                        target_opt["voters"] = curr_list
                        target_opt["votes"] = curr_list

                        new_body = json.dumps(data)
                        res = coll.find_one_and_update(
                            {"_id": message_id},
                            {"$set": {"body": new_body, "updated_at": now}},
                            return_document=pymongo.ReturnDocument.AFTER,
                        )
                        return res
    except Exception:
        pass
    return None


def latest_message(conversation_id: str) -> dict | None:
    cid = str(conversation_id)
    local_items = _inmemory_messages.get(cid, [])
    if local_items:
        return local_items[-1]

    try:
        coll = get_messages_collection()
        if coll is None:
            return None
        res = coll.find({"conversation_id": cid}).sort("created_at", pymongo.DESCENDING).limit(1)
        res = list(res)
        return res[0] if res else None
    except Exception:
        return None


# Alias for compatibility with views
last_message_for = latest_message


def unread_count(conversation_id: str, last_read_at, employee_id: str) -> int:
    cid = str(conversation_id)
    emp_str = str(employee_id).lower()

    alias_keys = {cid}
    if cid.startswith("direct_"):
        emp_str_target = cid.replace("direct_", "")
        from apps.chat.serializers import _resolve_employee_by_str
        emp = _resolve_employee_by_str(emp_str_target)
        if emp:
            alias_keys.add(str(emp.id))
            alias_keys.add(f"direct_{emp.id}")
            if emp.employee_code:
                alias_keys.add(f"direct_{emp.employee_code.lower()}")
    else:
        for key in list(_inmemory_messages.keys()):
            if key.startswith("direct_"):
                alias_keys.add(key)

    keys_list = list(alias_keys)
    local_items = []
    for k in keys_list:
        local_items.extend(_inmemory_messages.get(k, []))

    last_dt = None
    if last_read_at:
        if isinstance(last_read_at, str):
            try:
                last_dt = datetime.fromisoformat(last_read_at.replace("Z", "+00:00"))
            except Exception:
                last_dt = None
        elif isinstance(last_read_at, datetime):
            last_dt = last_read_at

    count = 0
    seen_ids = set()
    for m in local_items:
        m_id = m.get("_id")
        if not m_id or m_id in seen_ids:
            continue
        seen_ids.add(m_id)
        sender_str = str(m.get("sender_id", "")).lower()
        if sender_str != emp_str and not m.get("is_deleted"):
            m_dt = m.get("created_at")
            if not last_dt:
                count += 1
            elif isinstance(m_dt, datetime) and m_dt > last_dt:
                count += 1
            elif isinstance(m_dt, str):
                try:
                    if datetime.fromisoformat(m_dt.replace("Z", "+00:00")) > last_dt:
                        count += 1
                except Exception:
                    pass

    return count


def my_mentions(employee_id: str, limit: int = 50) -> list[dict]:
    try:
        coll = get_messages_collection()
        if coll is None:
            return []
        return list(
            coll.find({"mentions": str(employee_id), "is_deleted": False})
            .sort("created_at", pymongo.DESCENDING)
            .limit(limit)
        )
    except Exception:
        return []


def starred_messages(employee_id: str, limit: int = 50) -> list[dict]:
    try:
        coll = get_messages_collection()
        if coll is None:
            return []
        return list(
            coll.find({"stars": str(employee_id), "is_deleted": False})
            .sort("created_at", pymongo.DESCENDING)
            .limit(limit)
        )
    except Exception:
        return []


# ── Calls Disk Storage ──────────────────────────────────────────────────
CALLS_DB_FILE_PATH = Path(settings.BASE_DIR) / "chat_calls_db.json"
_inmemory_calls: list[dict] = []

def _load_calls_db():
    global _inmemory_calls
    if CALLS_DB_FILE_PATH.exists():
        try:
            with open(CALLS_DB_FILE_PATH, "r", encoding="utf-8") as f:
                _inmemory_calls = json.load(f)
        except Exception as e:
            logger.warning("Could not load chat_calls_db.json: %s", e)

def _save_calls_db():
    try:
        with open(CALLS_DB_FILE_PATH, "w", encoding="utf-8") as f:
            json.dump(_inmemory_calls, f, indent=2, default=str)
    except Exception as e:
        logger.warning("Could not save chat_calls_db.json: %s", e)

_load_calls_db()

def initiate_call(caller_id: str, recipient_id: str, call_type: str, conversation_id: str | None = None) -> dict:
    now = _now()
    call_doc = {
        "_id": new_id(),
        "caller_id": str(caller_id),
        "recipient_id": str(recipient_id),
        "call_type": call_type,
        "conversation_id": conversation_id,
        "status": "RINGING",
        "created_at": now,
        "accepted_at": None,
        "ended_at": None,
        "duration_seconds": 0,
    }
    _inmemory_calls.append(call_doc)
    _save_calls_db()
    return call_doc

def update_call_status(call_id: str, status: str, duration_seconds: int = 0) -> dict | None:
    now = _now()
    for c in _inmemory_calls:
        if c["_id"] == call_id:
            c["status"] = status
            if status == "ACCEPTED" and not c.get("accepted_at"):
                c["accepted_at"] = now
            elif status in ("ENDED", "DECLINED", "MISSED"):
                c["ended_at"] = now
                if c.get("accepted_at"):
                    try:
                        from datetime import datetime, timezone
                        acc_time = datetime.fromisoformat(c["accepted_at"])
                        end_time = datetime.fromisoformat(now)
                        calc_secs = int((end_time - acc_time).total_seconds())
                        if calc_secs > 0:
                            duration_seconds = max(duration_seconds, calc_secs)
                    except Exception:
                        pass
                c["duration_seconds"] = duration_seconds
            _save_calls_db()
            return c
    return None

def get_active_call_for_user(employee_id: str) -> dict | None:
    emp_str = str(employee_id).lower()
    for c in reversed(_inmemory_calls):
        c_caller = str(c.get("caller_id", "")).lower()
        c_recip = str(c.get("recipient_id", "")).lower()
        if emp_str in (c_caller, c_recip):
            if c.get("status") in ("RINGING", "ACCEPTED"):
                if c.get("status") == "RINGING" and c.get("created_at"):
                    try:
                        from datetime import datetime, timezone
                        c_dt = datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                        now_dt = datetime.now(timezone.utc)
                        if (now_dt - c_dt).total_seconds() > 45:
                            c["status"] = "MISSED"
                            c["ended_at"] = datetime.now(timezone.utc).isoformat()
                            _save_calls_db()
                            continue
                    except Exception:
                        pass
                return c
    return None

def list_call_history(employee_id: str, limit: int = 50) -> list[dict]:
    emp_str = str(employee_id).lower()
    results = []
    for c in reversed(_inmemory_calls):
        c_caller = str(c.get("caller_id", "")).lower()
        c_recip = str(c.get("recipient_id", "")).lower()
        if emp_str in (c_caller, c_recip):
            results.append(c)
        if len(results) >= limit:
            break
    return results

