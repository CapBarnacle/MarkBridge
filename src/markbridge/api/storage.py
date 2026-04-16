"""Storage helpers for API-level source acquisition."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from tempfile import mkstemp
from urllib.parse import urlparse

import boto3

from markbridge.shared.ir import DocumentFormat


SUPPORTED_SUFFIXES: dict[str, DocumentFormat] = {
    ".pdf": DocumentFormat.PDF,
    ".docx": DocumentFormat.DOCX,
    ".xlsx": DocumentFormat.XLSX,
    ".doc": DocumentFormat.DOC,
    ".hwp": DocumentFormat.HWP,
}


@dataclass(frozen=True, slots=True)
class S3ObjectRef:
    bucket: str
    key: str


def parse_s3_uri(s3_uri: str) -> S3ObjectRef:
    parsed = urlparse(s3_uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path.strip("/"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")
    return S3ObjectRef(bucket=parsed.netloc, key=parsed.path.lstrip("/"))


def download_s3_uri_to_tempfile(s3_uri: str, *, suffix: str = "") -> Path:
    ref = parse_s3_uri(s3_uri)
    fd, tmp_path = mkstemp(prefix="markbridge_", suffix=suffix)
    path = Path(tmp_path)
    try:
        client = boto3.client("s3")
        client.download_file(ref.bucket, ref.key, str(path))
    except Exception:
        path.unlink(missing_ok=True)
        raise
    finally:
        try:
            import os

            os.close(fd)
        except OSError:
            pass
    return path


@dataclass(frozen=True, slots=True)
class S3ObjectOption:
    bucket: str
    key: str
    size_bytes: int | None = None
    updated_at: datetime | None = None

    @property
    def s3_uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"

    @property
    def label(self) -> str:
        return self.key.split("/")[-1] or self.key

    @property
    def document_format(self) -> DocumentFormat | None:
        suffix = Path(self.key).suffix.lower()
        return SUPPORTED_SUFFIXES.get(suffix)


def list_s3_buckets() -> list[str]:
    client = boto3.client("s3")
    response = client.list_buckets()
    buckets = [str(item["Name"]) for item in response.get("Buckets", []) if item.get("Name")]
    return sorted(buckets)


def list_s3_objects(
    *,
    bucket: str,
    prefix: str = "",
    limit: int = 100,
) -> list[S3ObjectOption]:
    if not bucket.strip():
        raise ValueError("bucket is required")
    if limit <= 0:
        raise ValueError("limit must be greater than zero")

    client = boto3.client("s3")
    paginator = client.get_paginator("list_objects_v2")
    collected: list[S3ObjectOption] = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for item in page.get("Contents", []):
            key = str(item["Key"])
            option = S3ObjectOption(
                bucket=bucket,
                key=key,
                size_bytes=int(item.get("Size", 0)),
                updated_at=_normalize_timestamp(item.get("LastModified")),
            )
            if option.document_format is None:
                continue
            collected.append(option)
            if len(collected) >= limit:
                return collected
    return collected


def _normalize_timestamp(value: object) -> datetime | None:
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value
        return value.replace(tzinfo=timezone.utc)
    return None
