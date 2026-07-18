import boto3
from botocore.exceptions import ClientError
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


class S3Storage:
    def __init__(self, access_key, secret_key, bucket_name, endpoint_url):
        if endpoint_url and ":9001" in endpoint_url:
            endpoint_url = endpoint_url.replace(":9001", ":9000")
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
        )
        # Ensure bucket exists
        try:
            self.client.head_bucket(Bucket=self.bucket_name)
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code")
            if error_code in ("404", "NoSuchBucket"):
                try:
                    self.client.create_bucket(Bucket=self.bucket_name)
                except Exception:
                    pass
        except Exception:
            pass

    def upload_file(self, file_obj, object_name):
        if hasattr(file_obj, "seek"):
            try:
                file_obj.seek(0)
            except Exception:
                pass
        try:
            data = file_obj.read()
            if isinstance(data, str):
                data = data.encode("utf-8")
            from io import BytesIO
            file_data = BytesIO(data)
        except Exception:
            file_data = file_obj
        self.client.upload_fileobj(file_data, self.bucket_name, object_name)
        return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"

    def delete_file(self, object_name):
        try:
            self.client.delete_object(Bucket=self.bucket_name, Key=object_name)
        except Exception:
            pass

    def file_exists(self, object_name):
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except Exception:
            return False

    def get_file_size(self, object_name):
        try:
            response = self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return response.get("ContentLength", 0)
        except Exception:
            return 0

    def get_presigned_url(self, object_name, expiry=3600):
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
        except Exception:
            return None
            
        import mimetypes
        content_type, _ = mimetypes.guess_type(object_name)
        if not content_type:
            content_type = "application/pdf"
            
        presigned_url = self.client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_name,
                "ResponseContentDisposition": "inline",
                "ResponseContentType": content_type,
            },
            ExpiresIn=expiry,
        )
        
        # Rewrite URL using public endpoint if configured
        from decouple import config
        public_url = config("MINIO_PUBLIC_URL", default="").strip()
        if public_url and presigned_url:
            from urllib.parse import urlparse, urlunparse
            parsed_presigned = urlparse(presigned_url)
            parsed_public = urlparse(public_url)
            presigned_url = urlunparse(
                parsed_presigned._replace(
                    scheme=parsed_public.scheme,
                    netloc=parsed_public.netloc
                )
            )
                
        return presigned_url

    def generate_presigned_put_url(self, object_name, content_type="application/octet-stream", expiry=600):
        """Direct-upload URL: client PUTs the file straight to MinIO/S3, matching
        the get_object counterpart above (get_presigned_url) used for downloads."""
        presigned_url = self.client.generate_presigned_url(
            "put_object",
            Params={
                "Bucket": self.bucket_name,
                "Key": object_name,
                "ContentType": content_type,
            },
            ExpiresIn=expiry,
        )

        from decouple import config
        public_url = config("MINIO_PUBLIC_URL", default="").strip()
        if public_url and presigned_url:
            from urllib.parse import urlparse, urlunparse
            parsed_presigned = urlparse(presigned_url)
            parsed_public = urlparse(public_url)
            presigned_url = urlunparse(
                parsed_presigned._replace(scheme=parsed_public.scheme, netloc=parsed_public.netloc)
            )
        return presigned_url

    @staticmethod
    def format_file_size(size):
        if size is None:
            return None
        if size < 512_000:
            return f"{round(size / 1000, 2)} KB"
        elif size < 512_000_000:
            return f"{round(size / 1_000_000, 2)} MB"
        return f"{round(size / 1_000_000_000, 2)} GB"


@deconstructible
class DjangoS3Storage(Storage):
    def __init__(self, access_key="", secret_key="", bucket_name="", endpoint_url=""):
        self._s3 = S3Storage(access_key, secret_key, bucket_name, endpoint_url)

    def _open(self, name, mode="rb"):
        raise NotImplementedError

    def _save(self, name, content):
        try:
            content.seek(0)
        except Exception:
            pass
        self._s3.upload_file(content, name)
        return name

    def delete(self, name):
        self._s3.delete_file(name)

    def exists(self, name):
        return self._s3.file_exists(name)

    def size(self, name):
        return self._s3.get_file_size(name)

    def url(self, name):
        return self._s3.get_presigned_url(name)
