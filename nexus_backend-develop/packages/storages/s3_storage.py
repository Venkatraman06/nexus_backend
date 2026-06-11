import boto3
from botocore.exceptions import ClientError
from django.core.files.storage import Storage
from django.utils.deconstruct import deconstructible


class S3Storage:
    def __init__(self, access_key, secret_key, bucket_name, endpoint_url):
        self.bucket_name = bucket_name
        self.endpoint_url = endpoint_url
        self.client = boto3.client(
            "s3",
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            endpoint_url=endpoint_url,
        )

    def upload_file(self, file_obj, object_name):
        self.client.upload_fileobj(file_obj, self.bucket_name, object_name)
        return f"{self.endpoint_url}/{self.bucket_name}/{object_name}"

    def delete_file(self, object_name):
        self.client.delete_object(Bucket=self.bucket_name, Key=object_name)

    def file_exists(self, object_name):
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
            return True
        except ClientError:
            return False

    def get_file_size(self, object_name):
        response = self.client.head_object(Bucket=self.bucket_name, Key=object_name)
        return response.get("ContentLength", 0)

    def get_presigned_url(self, object_name, expiry=3600):
        try:
            self.client.head_object(Bucket=self.bucket_name, Key=object_name)
        except ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return None
            raise
        return self.client.generate_presigned_url(
            "get_object",
            Params={"Bucket": self.bucket_name, "Key": object_name},
            ExpiresIn=expiry,
        )

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
        self._s3.upload_file(content.file, name)
        return name

    def delete(self, name):
        self._s3.delete_file(name)

    def exists(self, name):
        return self._s3.file_exists(name)

    def size(self, name):
        return self._s3.get_file_size(name)

    def url(self, name):
        return self._s3.get_presigned_url(name)
