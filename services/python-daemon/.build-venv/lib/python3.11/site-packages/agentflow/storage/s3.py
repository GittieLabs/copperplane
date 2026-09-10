"""
S3-compatible storage backend.

Implements StorageBackend using boto3. Works with:
- AWS S3
- Railway Storage (t3.storageapi.dev)
- MinIO (local dev)

Configure via environment variables:
    S3_ENDPOINT         — endpoint URL (e.g., https://t3.storageapi.dev)
    S3_ACCESS_KEY_ID    — access key
    S3_SECRET_ACCESS_KEY — secret key
    S3_BUCKET           — bucket name (default: openclaw)
    S3_REGION           — region (default: us-east-1)
"""
from __future__ import annotations

import logging

logger = logging.getLogger("agentflow.storage.s3")

try:
    import boto3
    from botocore.exceptions import ClientError
except ImportError:
    boto3 = None  # type: ignore[assignment]
    ClientError = Exception  # type: ignore[assignment,misc]


class S3Storage:
    """
    StorageBackend implementation backed by S3-compatible object storage.

    All paths are treated as S3 object keys within the configured bucket.
    Text content is stored as UTF-8.
    """

    def __init__(
        self,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
        bucket: str = "openclaw",
        region: str = "us-east-1",
    ) -> None:
        if boto3 is None:
            raise ImportError("Install boto3: pip install agentflow[s3]")

        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=region,
        )

        # Ensure bucket exists
        try:
            self._client.head_bucket(Bucket=bucket)
        except ClientError:
            logger.info("Creating S3 bucket: %s", bucket)
            try:
                self._client.create_bucket(Bucket=bucket)
            except ClientError:
                logger.warning("Could not create bucket %s (may already exist)", bucket)

    async def read(self, path: str) -> str | None:
        """Read an object as UTF-8 text. Returns None if not found."""
        try:
            response = self._client.get_object(Bucket=self._bucket, Key=path)
            return response["Body"].read().decode("utf-8")
        except ClientError as e:
            if e.response["Error"]["Code"] in ("NoSuchKey", "404"):
                return None
            raise

    async def write(self, path: str, content: str) -> None:
        """Write UTF-8 text content to an S3 object."""
        self._client.put_object(
            Bucket=self._bucket,
            Key=path,
            Body=content.encode("utf-8"),
            ContentType="text/plain; charset=utf-8",
        )

    async def exists(self, path: str) -> bool:
        """Check if an object exists."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=path)
            return True
        except ClientError:
            return False

    async def list(self, prefix: str) -> list[str]:
        """List all object keys under a prefix."""
        keys: list[str] = []
        paginator = self._client.get_paginator("list_objects_v2")

        for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                keys.append(obj["Key"])

        return sorted(keys)

    async def delete(self, path: str) -> None:
        """Delete an object."""
        try:
            self._client.delete_object(Bucket=self._bucket, Key=path)
        except ClientError:
            pass  # Silently ignore if already deleted

    @classmethod
    def from_env(cls) -> S3Storage:
        """Create from environment variables."""
        import os

        return cls(
            endpoint_url=os.environ["S3_ENDPOINT"],
            access_key_id=os.environ["S3_ACCESS_KEY_ID"],
            secret_access_key=os.environ["S3_SECRET_ACCESS_KEY"],
            bucket=os.getenv("S3_BUCKET", "openclaw"),
            region=os.getenv("S3_REGION", "us-east-1"),
        )
