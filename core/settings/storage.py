from decouple import config

# In development (DEBUG=True), use local filesystem storage for uploaded files.
# In production (DEBUG=False), use MinIO/S3.
_debug = config("DEBUG", default=False, cast=bool)
_use_local = config("DJANGO_USE_LOCAL_STORAGE", default=str(_debug)).lower() in ("true", "1", "yes")

if _use_local:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "packages.storages.dynamic_storage.DynamicS3Storage",
            "OPTIONS": {
                "endpoint_url": config("MINIO_ENDPOINT_URL", default="http://localhost:9000"),
                "access_key": config("MINIO_ACCESS_KEY", default="minioadmin"),
                "secret_key": config("MINIO_SECRET_KEY", default="minioadmin"),
                "bucket_name": config("MINIO_BUCKET_NAME", default="pmt-files"),
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }
