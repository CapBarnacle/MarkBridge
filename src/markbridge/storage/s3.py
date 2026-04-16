"""S3 storage helpers using the runtime IAM role."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

import boto3


@dataclass(frozen=True, slots=True)
class S3ObjectRef:
    bucket: str
    key: str

    @property
    def uri(self) -> str:
        return f"s3://{self.bucket}/{self.key}"


def parse_s3_uri(uri: str) -> S3ObjectRef:
    parsed = urlparse(uri)
    if parsed.scheme != "s3" or not parsed.netloc or not parsed.path:
        raise ValueError(f"Invalid S3 URI: {uri}")
    return S3ObjectRef(bucket=parsed.netloc, key=parsed.path.lstrip("/"))


class S3Storage:
    """Thin S3 wrapper that relies on the ambient AWS role."""

    def __init__(self) -> None:
        self._client = boto3.client("s3")

    def download(self, uri: str, destination: Path) -> Path:
        ref = parse_s3_uri(uri)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._client.download_file(ref.bucket, ref.key, str(destination))
        return destination
