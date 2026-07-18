from packages.storages.dynamic_storage import _get_config
from packages.storages.s3_storage import S3Storage

# Presigned direct-to-MinIO uploads need a real S3 endpoint the browser can
# reach — there's no local-disk fallback equivalent for a client PUT, unlike
# DynamicS3Storage's read/write fallback. Reuses the same config resolution
# (env vars / STORAGES OPTIONS) that DynamicS3Storage already uses.
_storage = None


def get_chat_s3_storage() -> S3Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage(**_get_config())
    return _storage
