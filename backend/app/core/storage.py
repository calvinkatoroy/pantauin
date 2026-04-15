"""
Evidence file storage abstraction.

Two modes:
- Local (default): screenshots saved under settings.evidence_dir, served as
  static files by FastAPI.
- S3/R2 (when S3_BUCKET + credentials are set): screenshots uploaded to S3/R2,
  served via presigned URLs or a public base URL.

The screenshot_path stored in the DB is always in the format
"{scan_id}/{filename}" regardless of storage mode. The storage layer
resolves that key to a local path or a URL at serve time.
"""
import logging
import os
from functools import lru_cache
from typing import Optional

from app.core.config import settings

logger = logging.getLogger(__name__)


def _s3_configured() -> bool:
    return bool(settings.s3_bucket and settings.s3_access_key_id and settings.s3_secret_access_key)


@lru_cache(maxsize=1)
def _get_s3_client():
    """Return a boto3 S3 client, cached for the process lifetime."""
    import boto3  # type: ignore

    kwargs: dict = {
        "aws_access_key_id": settings.s3_access_key_id,
        "aws_secret_access_key": settings.s3_secret_access_key,
    }
    if settings.s3_endpoint_url:
        kwargs["endpoint_url"] = settings.s3_endpoint_url
    else:
        kwargs["region_name"] = "auto"

    return boto3.client("s3", **kwargs)


def upload_evidence(local_path: str, object_key: str) -> bool:
    """
    Upload a local file to S3/R2 under object_key.
    Returns True on success, False if S3 is not configured or upload fails.
    After a successful upload the local file is deleted.
    """
    if not _s3_configured():
        return False

    try:
        client = _get_s3_client()
        client.upload_file(
            local_path,
            settings.s3_bucket,
            object_key,
            ExtraArgs={"ContentType": "image/png"},
        )
        os.remove(local_path)
        logger.debug("Uploaded evidence to S3: %s", object_key)
        return True
    except Exception as exc:
        logger.error("S3 upload failed for %s: %s", object_key, exc)
        return False


def get_evidence_url(object_key: str) -> Optional[str]:
    """
    Return a URL to access the evidence file.

    - If a public base URL is configured (S3_PUBLIC_URL), return a direct URL.
    - Otherwise generate a presigned URL (valid for S3_PRESIGN_EXPIRY seconds).
    - Returns None if S3 is not configured (caller falls back to /evidence/ static route).
    """
    if not _s3_configured():
        return None

    if settings.s3_public_url:
        base = settings.s3_public_url.rstrip("/")
        return f"{base}/{object_key}"

    try:
        client = _get_s3_client()
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": object_key},
            ExpiresIn=settings.s3_presign_expiry,
        )
        return url
    except Exception as exc:
        logger.error("Failed to generate presigned URL for %s: %s", object_key, exc)
        return None


def delete_evidence(object_key: str) -> bool:
    """Delete an object from S3/R2. Returns True on success."""
    if not _s3_configured():
        return False

    try:
        client = _get_s3_client()
        client.delete_object(Bucket=settings.s3_bucket, Key=object_key)
        return True
    except Exception as exc:
        logger.error("S3 delete failed for %s: %s", object_key, exc)
        return False


def delete_evidence_prefix(prefix: str) -> bool:
    """Delete all objects under a prefix (e.g. a scan_id folder)."""
    if not _s3_configured():
        return False

    try:
        client = _get_s3_client()
        paginator = client.get_paginator("list_objects_v2")
        pages = paginator.paginate(Bucket=settings.s3_bucket, Prefix=prefix)
        keys = [
            {"Key": obj["Key"]}
            for page in pages
            for obj in page.get("Contents", [])
        ]
        if keys:
            client.delete_objects(Bucket=settings.s3_bucket, Delete={"Objects": keys})
        return True
    except Exception as exc:
        logger.error("S3 prefix delete failed for %s: %s", prefix, exc)
        return False
