from decouple import config
from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage

from .s3_storage import DjangoS3Storage


def _get_config():
    """MinIO/S3 settings — STORAGES OPTIONS first, then env (works in local-dev mode)."""
    opts = settings.STORAGES.get("default", {}).get("OPTIONS", {})
    endpoint = opts.get("endpoint_url") or config(
        "MINIO_ENDPOINT_URL", default="http://localhost:9000",
    )
    if endpoint and ":9001" in endpoint:
        endpoint = endpoint.replace(":9001", ":9000")
    return {
        "access_key": opts.get("access_key") or config("MINIO_ACCESS_KEY", default="minioadmin"),
        "secret_key": opts.get("secret_key") or config("MINIO_SECRET_KEY", default="minioadmin"),
        "bucket_name": opts.get("bucket_name") or config("MINIO_BUCKET_NAME", default="pmt-files"),
        "endpoint_url": endpoint,
    }


def _minio_ready(cfg: dict) -> bool:
    endpoint = (cfg.get("endpoint_url") or "").strip()
    bucket = (cfg.get("bucket_name") or "").strip()
    if not endpoint or not bucket:
        return False
    
    # Quick socket connection check to avoid hanging/throwing if MinIO is not running
    try:
        from urllib.parse import urlparse
        import socket
        parsed = urlparse(endpoint)
        host = parsed.hostname
        port = parsed.port or (80 if parsed.scheme == "http" else 443)
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except Exception:
        return False


class DynamicS3Storage(Storage):
    """Upload to MinIO/S3 when configured; otherwise fall back to local media."""

    def __init__(self, **kwargs):
        self._cached_backend = None
        self._local_backend = FileSystemStorage()

    @property
    def _backend(self):
        if self._cached_backend is None:
            cfg = _get_config()
            if _minio_ready(cfg):
                self._cached_backend = DjangoS3Storage(**cfg)
            else:
                self._cached_backend = self._local_backend
        return self._cached_backend

    def _save(self, name, content):
        backend = self._backend
        if not isinstance(backend, FileSystemStorage):
            try:
                return backend._save(name, content)
            except Exception as e:
                import logging
                logging.getLogger("django").warning(
                    f"S3 save failed ({e}), falling back to local FileSystemStorage."
                )
        return self._local_backend._save(name, content)

    def _open(self, name, mode="rb"):
        if self._local_backend.exists(name):
            return self._local_backend._open(name, mode)
        return self._backend._open(name, mode)

    def delete(self, name):
        if self._local_backend.exists(name):
            self._local_backend.delete(name)
        try:
            self._backend.delete(name)
        except Exception:
            pass

    def exists(self, name):
        if self._local_backend.exists(name):
            return True
        try:
            return self._backend.exists(name)
        except Exception:
            return False

    def url(self, name):
        if self._local_backend.exists(name):
            return self._local_backend.url(name)
        try:
            return self._backend.url(name)
        except Exception:
            return self._local_backend.url(name)

    def size(self, name):
        if self._local_backend.exists(name):
            return self._local_backend.size(name)
        try:
            return self._backend.size(name)
        except Exception:
            return 0

