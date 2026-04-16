from datetime import datetime, timezone
from pathlib import Path

import markbridge.storage.s3 as domain_s3
import markbridge.api.storage as api_storage
from markbridge.api.storage import list_s3_buckets, list_s3_objects, parse_s3_uri as parse_api_s3_uri
from markbridge.storage.s3 import parse_s3_uri


def test_parse_s3_uri_helpers() -> None:
    api_ref = parse_api_s3_uri("s3://bucket/path/to/file.xlsx")
    domain_ref = parse_s3_uri("s3://bucket/path/to/file.xlsx")

    assert api_ref.bucket == "bucket"
    assert api_ref.key == "path/to/file.xlsx"
    assert domain_ref.bucket == "bucket"
    assert domain_ref.key == "path/to/file.xlsx"


def test_domain_s3_download_calls_boto3(monkeypatch, tmp_path: Path) -> None:
    calls: list[tuple[str, str, str]] = []

    class FakeClient:
        def download_file(self, bucket: str, key: str, dest: str) -> None:
            calls.append((bucket, key, dest))
            Path(dest).write_bytes(b"data")

    monkeypatch.setattr(domain_s3.boto3, "client", lambda service: FakeClient())

    storage = domain_s3.S3Storage()
    destination = tmp_path / "sample.bin"
    output = storage.download("s3://bucket/path/file.pdf", destination)

    assert output == destination
    assert destination.read_bytes() == b"data"
    assert calls == [("bucket", "path/file.pdf", str(destination))]


def test_api_s3_list_objects_filters_supported_formats(monkeypatch) -> None:
    class FakePaginator:
        def paginate(self, Bucket: str, Prefix: str):
            assert Bucket == "bucket"
            assert Prefix == "incoming/"
            return [
                {
                    "Contents": [
                        {
                            "Key": "incoming/sample.pdf",
                            "Size": 10,
                            "LastModified": datetime(2026, 4, 3, 8, 20, tzinfo=timezone.utc),
                        },
                        {
                            "Key": "incoming/notes.txt",
                            "Size": 20,
                            "LastModified": datetime(2026, 4, 3, 8, 21, tzinfo=timezone.utc),
                        },
                    ]
                }
            ]

    class FakeClient:
        def get_paginator(self, name: str) -> FakePaginator:
            assert name == "list_objects_v2"
            return FakePaginator()

    monkeypatch.setattr(api_storage.boto3, "client", lambda service: FakeClient())

    objects = list_s3_objects(bucket="bucket", prefix="incoming/")

    assert len(objects) == 1
    assert objects[0].s3_uri == "s3://bucket/incoming/sample.pdf"
    assert objects[0].label == "sample.pdf"


def test_api_s3_list_buckets_returns_sorted_names(monkeypatch) -> None:
    class FakeClient:
        def list_buckets(self):
            return {"Buckets": [{"Name": "zeta-bucket"}, {"Name": "alpha-bucket"}]}

    monkeypatch.setattr(api_storage.boto3, "client", lambda service: FakeClient())

    buckets = list_s3_buckets()

    assert buckets == ["alpha-bucket", "zeta-bucket"]
