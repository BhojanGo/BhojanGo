"""File storage for uploads (P18): delivery-proof photos and rider documents.

local: files under LOCAL_STORAGE_DIR (tests, and any machine without LocalStack).
s3:    the UPLOADS_BUCKET bucket (LocalStack in `make dev`, S3 in production).

Keys are "<purpose>/<user id>/<uuid>.<ext>", so a key says who uploaded it.
Files are private: nothing here hands out public URLs.
"""
import asyncio
from pathlib import Path
from typing import Protocol

from shared.config import get_settings
from shared.providers import ProviderConfigError, refuse_in_production


class Storage(Protocol):
    name: str

    async def put(self, key: str, data: bytes, content_type: str) -> None: ...

    async def exists(self, key: str) -> bool: ...


class LocalStorage:
    name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root.resolve() not in path.parents:
            raise ValueError("Bad storage key")
        return path

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    async def exists(self, key: str) -> bool:
        return self._path(key).is_file()


class S3Storage:
    name = "s3"

    def __init__(self, bucket: str) -> None:
        self.bucket = bucket

    def _client(self):  # type: ignore[no-untyped-def]
        import boto3

        s = get_settings()
        kwargs: dict = {"region_name": s.AWS_REGION, "aws_access_key_id": s.AWS_ACCESS_KEY_ID or None,
                        "aws_secret_access_key": s.AWS_SECRET_ACCESS_KEY or None}
        if s.AWS_ENDPOINT_URL:
            kwargs["endpoint_url"] = s.AWS_ENDPOINT_URL
        return boto3.client("s3", **kwargs)

    async def put(self, key: str, data: bytes, content_type: str) -> None:
        await asyncio.to_thread(self._client().put_object, Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    async def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            await asyncio.to_thread(self._client().head_object, Bucket=self.bucket, Key=key)
            return True
        except ClientError:
            return False


def get_storage() -> Storage:
    p = get_settings().providers
    if p.STORAGE_PROVIDER == "local":
        refuse_in_production("Storage", "local")
        return LocalStorage(p.LOCAL_STORAGE_DIR)
    if p.STORAGE_PROVIDER == "s3":
        return S3Storage(p.UPLOADS_BUCKET)
    raise ProviderConfigError(f"Unknown STORAGE_PROVIDER '{p.STORAGE_PROVIDER}' (local | s3)")
