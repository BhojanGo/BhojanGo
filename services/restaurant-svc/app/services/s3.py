"""S3 presigned URL generation for image uploads."""
import uuid

import boto3
import structlog
from botocore.exceptions import ClientError

from app.config import get_settings

logger = structlog.get_logger(__name__)
settings = get_settings()


def get_s3_client():  # type: ignore[no-untyped-def]
    kwargs: dict = {
        "region_name": settings.AWS_REGION,
        "aws_access_key_id": settings.AWS_ACCESS_KEY_ID or None,
        "aws_secret_access_key": settings.AWS_SECRET_ACCESS_KEY or None,
    }
    if settings.AWS_ENDPOINT_URL:
        kwargs["endpoint_url"] = settings.AWS_ENDPOINT_URL
    return boto3.client("s3", **kwargs)


def generate_presigned_upload_url(
    file_type: str,
    folder: str = "restaurants",
    expiry_seconds: int = 900,
) -> dict:
    """Returns a presigned POST data dict for direct browser → S3 upload."""
    s3 = get_s3_client()
    key = f"{folder}/{uuid.uuid4()}.{file_type.split('/')[-1]}"

    try:
        response = s3.generate_presigned_post(
            Bucket=settings.AWS_S3_BUCKET,
            Key=key,
            Fields={"Content-Type": file_type},
            Conditions=[
                {"Content-Type": file_type},
                ["content-length-range", 1, 5 * 1024 * 1024],  # max 5MB
            ],
            ExpiresIn=expiry_seconds,
        )
        cdn_base = settings.AWS_CLOUDFRONT_URL or f"https://{settings.AWS_S3_BUCKET}.s3.amazonaws.com"
        return {
            "upload_url": response["url"],
            "fields": response["fields"],
            "file_url": f"{cdn_base}/{key}",
            "expires_in": expiry_seconds,
        }
    except ClientError as e:
        logger.error("s3_presigned_url_failed", error=str(e))
        raise
