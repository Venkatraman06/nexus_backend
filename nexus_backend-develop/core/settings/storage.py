from decouple import config

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
