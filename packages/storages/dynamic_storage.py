from django.conf import settings
from django.core.files.storage import Storage

from .s3_storage import DjangoS3Storage


def _get_config():
    opts = settings.STORAGES.get("default", {}).get("OPTIONS", {})
    return {
        "access_key": opts.get("access_key", ""),
        "secret_key": opts.get("secret_key", ""),
        "bucket_name": opts.get("bucket_name", ""),
        "endpoint_url": opts.get("endpoint_url", ""),
    }


class DynamicS3Storage(Storage):
    """Resolves MinIO/S3 config at runtime from settings.

    Django's STORAGES handler passes OPTIONS as kwargs on instantiation;
    we accept and ignore them because config is read lazily from settings.
    """

    def __init__(self, **kwargs):
        pass

    @property
    def _backend(self):
        return DjangoS3Storage(**_get_config())

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
