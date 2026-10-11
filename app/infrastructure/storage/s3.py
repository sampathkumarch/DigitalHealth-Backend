import logging

from app.core.config import Settings
from app.core.exceptions import ServiceUnavailable

logger = logging.getLogger(__name__)


class S3Storage:
    def __init__(self, settings: Settings) -> None:
        import boto3

        self.bucket_name = settings.s3_bucket
        self._ttl = settings.s3_presign_ttl_seconds
        kwargs: dict[str, str] = {"region_name": settings.aws_region}
        if settings.aws_access_key_id:
            kwargs["aws_access_key_id"] = settings.aws_access_key_id
            kwargs["aws_secret_access_key"] = settings.aws_secret_access_key
        if settings.s3_endpoint_url:
            kwargs["endpoint_url"] = settings.s3_endpoint_url
        self._client = boto3.client("s3", **kwargs)

    def put(self, key: str, data: bytes, content_type: str) -> None:
        try:
            self._client.put_object(
                Bucket=self.bucket_name,
                Key=key,
                Body=data,
                ContentType=content_type,
                ContentLength=len(data),
            )
        except Exception as exc:
            logger.exception("s3 upload failed")
            raise ServiceUnavailable("File storage is unavailable.") from exc

    def delete(self, key: str) -> None:
        try:
            self._client.delete_object(Bucket=self.bucket_name, Key=key)
        except Exception:
            logger.exception("s3 delete failed")

    def open_url(self, key: str) -> str | None:
        try:
            return self._client.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.bucket_name, "Key": key},
                ExpiresIn=self._ttl,
            )
        except Exception as exc:
            logger.exception("s3 presign failed")
            raise ServiceUnavailable("File storage is unavailable.") from exc

    def local_path(self, key: str) -> str | None:
        return None
