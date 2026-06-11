import logging
import socket
import urllib.parse
from django.conf import settings
from django.core.files.storage import Storage, FileSystemStorage

from .s3_storage import DjangoS3Storage

logger = logging.getLogger(__name__)


def _get_config():
    opts = settings.STORAGES.get("default", {}).get("OPTIONS", {})
    return {
        "access_key": opts.get("access_key", ""),
        "secret_key": opts.get("secret_key", ""),
        "bucket_name": opts.get("bucket_name", ""),
        "endpoint_url": opts.get("endpoint_url", ""),
    }


def _is_s3_reachable():
    try:
        opts = settings.STORAGES.get("default", {}).get("OPTIONS", {})
        endpoint_url = opts.get("endpoint_url", "")
        if not endpoint_url:
            return False
        url = urllib.parse.urlparse(endpoint_url)
        host = url.hostname or "localhost"
        port = url.port or (443 if url.scheme == "https" else 80)
        # 0.5s timeout socket connection check
        s = socket.create_connection((host, port), timeout=0.5)
        s.close()
        return True
    except Exception:
        return False


class DynamicS3Storage(Storage):
    """Resolves MinIO/S3 config at runtime from settings.

    Django's STORAGES handler passes OPTIONS as kwargs on instantiation;
    we accept and ignore them because config is read lazily from settings.
    """

    def __init__(self, **kwargs):
        self._local_fallback = FileSystemStorage()

    @property
    def _use_s3(self):
        return _is_s3_reachable()

    @property
    def _backend(self):
        return DjangoS3Storage(**_get_config())

    def _save(self, name, content):
        if self._use_s3:
            # Read content bytes in memory to ensure we can fall back even if S3 closes the file
            content_bytes = None
            try:
                pos = content.tell()
                content_bytes = content.read()
                content.seek(pos)
            except Exception:
                pass

            try:
                return self._backend._save(name, content)
            except Exception as exc:
                logger.warning("S3/MinIO upload failed (%s); falling back to local FileSystemStorage.", exc)
                if content_bytes is not None:
                    from django.core.files.base import ContentFile
                    fallback_content = ContentFile(content_bytes)
                    return self._local_fallback._save(name, fallback_content)
                else:
                    try:
                        content.seek(0)
                    except Exception:
                        pass
                    return self._local_fallback._save(name, content)
        return self._local_fallback._save(name, content)

    def _open(self, name, mode="rb"):
        if self._local_fallback.exists(name):
            return self._local_fallback._open(name, mode)
        if self._use_s3:
            try:
                return self._backend._open(name, mode)
            except Exception as exc:
                logger.warning("S3/MinIO open failed (%s); falling back to local FileSystemStorage.", exc)
        return self._local_fallback._open(name, mode)

    def delete(self, name):
        if self._local_fallback.exists(name):
            return self._local_fallback.delete(name)
        if self._use_s3:
            try:
                return self._backend.delete(name)
            except Exception as exc:
                logger.warning("S3/MinIO delete failed (%s); falling back to local FileSystemStorage.", exc)

    def exists(self, name):
        if self._local_fallback.exists(name):
            return True
        if self._use_s3:
            try:
                return self._backend.exists(name)
            except Exception as exc:
                logger.warning("S3/MinIO exists failed (%s); falling back to local FileSystemStorage.", exc)
        return self._local_fallback.exists(name)

    def url(self, name):
        if self._local_fallback.exists(name):
            return self._local_fallback.url(name)
        if self._use_s3:
            try:
                return self._backend.url(name)
            except Exception as exc:
                logger.warning("S3/MinIO url generation failed (%s); falling back to local FileSystemStorage.", exc)
        return self._local_fallback.url(name)

    def size(self, name):
        if self._local_fallback.exists(name):
            return self._local_fallback.size(name)
        if self._use_s3:
            try:
                return self._backend.size(name)
            except Exception as exc:
                logger.warning("S3/MinIO size check failed (%s); falling back to local FileSystemStorage.", exc)
        return self._local_fallback.size(name)
