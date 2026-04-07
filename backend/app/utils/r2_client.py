"""
app/utils/r2_client.py — Cloudflare R2 object storage client.

Cloudflare R2 is S3-compatible, so we use boto3 with a custom endpoint URL
derived from the R2 account ID.  Files are uploaded and served via a public
CDN URL configured in settings.
"""

from __future__ import annotations

import boto3
from botocore.client import BaseClient

from app.config import settings

# ---------------------------------------------------------------------------
# R2 endpoint
# ---------------------------------------------------------------------------
# Cloudflare R2 endpoints follow the pattern:
#   https://<account_id>.r2.cloudflarestorage.com
_R2_ENDPOINT_URL = (
    f"https://{settings.R2_ACCOUNT_ID}.r2.cloudflarestorage.com"
)


def get_r2_client() -> BaseClient:
    """
    Return a configured boto3 S3 client pointing at Cloudflare R2.

    The client uses:
      - The R2-specific endpoint URL (not the default AWS S3 endpoint).
      - The R2 API token key pair from settings.
      - region_name="auto" because R2 doesn't use regions in the traditional
        AWS sense but boto3 requires the parameter.
    """
    return boto3.client(
        "s3",
        endpoint_url=_R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
    )


async def upload_file(key: str, data: bytes, content_type: str) -> str:
    """
    Upload *data* to R2 under *key* and return the public CDN URL.

    Args:
        key:          Object key (path) within the bucket, e.g. "audio/abc123.mp3".
        data:         Raw bytes to upload.
        content_type: MIME type, e.g. "audio/mpeg".

    Returns:
        Fully-qualified public URL for the uploaded file,
        e.g. "https://cdn.example.com/audio/abc123.mp3".

    Note:
        boto3 is a synchronous library.  For production workloads with high
        concurrency, consider running this in a thread pool executor via
        asyncio.get_event_loop().run_in_executor().
    """
    import asyncio

    client = get_r2_client()

    # Run the synchronous boto3 call in a thread pool so the event loop is
    # not blocked during the network upload.
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        lambda: client.put_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=content_type,
            # Make the object publicly readable via the CDN URL.
            ACL="public-read",
        ),
    )

    # Construct the public URL from the configured CDN base URL.
    public_url = f"{settings.R2_PUBLIC_URL.rstrip('/')}/{key}"
    return public_url
