import io
import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

from . import mongo
from .storage import get_chat_s3_storage

logger = logging.getLogger(__name__)


@shared_task(name="chat.scan_attachment")
def scan_attachment(message_id, attachment_id):
    message = mongo.get_message(message_id)
    if message is None:
        return
    attachment = next((a for a in message.get("attachments", []) if a["id"] == attachment_id), None)
    if attachment is None:
        return

    try:
        import clamd

        storage = get_chat_s3_storage()
        buffer = io.BytesIO()
        storage.client.download_fileobj(storage.bucket_name, attachment["object_key"], buffer)
        buffer.seek(0)

        cd = clamd.ClamdNetworkSocket(host=settings.CLAMAV_HOST, port=settings.CLAMAV_PORT)
        result = cd.instream(buffer)
        stream_status = result.get("stream", (None,))[0]

        if stream_status == "OK":
            new_status = "CLEAN"
        elif stream_status == "FOUND":
            new_status = "INFECTED"
            storage.delete_file(attachment["object_key"])
            logger.warning("Infected chat attachment quarantined: %s", attachment["object_key"])
        else:
            new_status = "ERROR"
    except Exception:
        logger.exception("ClamAV scan failed for attachment %s", attachment_id)
        new_status = "ERROR"

    mongo.update_attachment_scan_status(message_id, attachment_id, new_status, timezone.now())

    # Let any open chat thread pick up the new scan_status/download_url live
    # instead of staying stuck showing "pending" until the user reloads.
    updated = mongo.get_message(message_id)
    if updated is not None:
        from apps.accounts.models import Employee
        from .realtime import RequestContext, broadcast_to_conversation
        from .serializers import MessageSerializer

        sender = Employee.objects.filter(id=updated.get("sender_id")).first()
        if sender is not None:
            data = MessageSerializer(updated, context={"request": RequestContext(sender)}).data
            broadcast_to_conversation(updated["conversation_id"], "chat.message.updated", data)
