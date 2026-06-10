from decouple import config
from django.conf import settings
from django.core.files.storage import FileSystemStorage, Storage

from .s3_storage import DjangoS3Storage


def _get_config():
    """MinIO/S3 settings — STORAGES OPTIONS first, then env (works in local-dev mode)."""
    opts = settings.STORAGES.get("default", {}).get("OPTIONS", {})
    return {
        "access_key": opts.get("access_key") or config("MINIO_ACCESS_KEY", default="minioadmin"),
        "secret_key": opts.get("secret_key") or config("MINIO_SECRET_KEY", default="minioadmin"),
        "bucket_name": opts.get("bucket_name") or config("MINIO_BUCKET_NAME", default="pmt-files"),
        "endpoint_url": opts.get("endpoint_url") or config(
            "MINIO_ENDPOINT_URL", default="http://localhost:9000",
        ),
    }


def _minio_ready(cfg: dict) -> bool:
    return bool((cfg.get("endpoint_url") or "").strip() and (cfg.get("bucket_name") or "").strip())


class DynamicS3Storage(Storage):
    """Upload to MinIO/S3 when configured; otherwise fall back to local media."""

    def __init__(self, **kwargs):
        self._cached_backend = None

    @property
    def _backend(self):
        if self._cached_backend is None:
            cfg = _get_config()
            if _minio_ready(cfg):
                self._cached_backend = DjangoS3Storage(**cfg)
            else:
                self._cached_backend = FileSystemStorage()
        return self._cached_backend

    def _save(self, name, content):
        return self._backend._save(name, content)

    def _open(self, name, mode="rb"):
        return self._backend._open(name, mode)

    def delete(self, name):
        return self._backend.delete(name)

    def exists(self, name):
        return self._backend.exists(name)

    def url(self, name):
        return self._backend.url(name)

    def size(self, name):
        return self._backend.size(name)
