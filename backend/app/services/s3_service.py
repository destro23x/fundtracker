"""
Serwis S3 — obsługa LocalStack / AWS S3.

Używa boto3 synchronicznie (wywołania są szybkie i uruchamiane w krótkich
transakcjach, nie w pętlach async). Do użycia przez endpointy FastAPI.
"""

from __future__ import annotations

import io
from typing import Any

import boto3
from botocore.exceptions import ClientError

from app.config import get_settings


def _client():
    cfg = get_settings()
    return boto3.client(
        "s3",
        endpoint_url=cfg.aws_endpoint_url,
        aws_access_key_id=cfg.aws_access_key_id,
        aws_secret_access_key=cfg.aws_secret_access_key,
        region_name=cfg.aws_region,
    )


def _ensure_bucket(client, bucket: str) -> None:
    """Tworzy bucket jeśli nie istnieje (przydatne w dev/LocalStack)."""
    try:
        client.head_bucket(Bucket=bucket)
    except ClientError as e:
        if e.response["Error"]["Code"] in ("404", "NoSuchBucket"):
            client.create_bucket(
                Bucket=bucket,
                CreateBucketConfiguration={"LocationConstraint": get_settings().aws_region},
            )
        else:
            raise


def upload_file(key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
    """Uploaduje plik do S3. Zwraca klucz (key)."""
    cfg = get_settings()
    client = _client()
    _ensure_bucket(client, cfg.s3_bucket)
    client.put_object(
        Bucket=cfg.s3_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return key


def download_file(key: str) -> bytes:
    """Pobiera plik z S3 jako bytes."""
    cfg = get_settings()
    client = _client()
    resp = client.get_object(Bucket=cfg.s3_bucket, Key=key)
    return resp["Body"].read()


def list_files(prefix: str) -> list[dict[str, Any]]:
    """Zwraca listę obiektów S3 z podanym prefiksem."""
    cfg = get_settings()
    client = _client()
    try:
        _ensure_bucket(client, cfg.s3_bucket)
        paginator = client.get_paginator("list_objects_v2")
        result = []
        for page in paginator.paginate(Bucket=cfg.s3_bucket, Prefix=prefix):
            for obj in page.get("Contents", []):
                result.append({
                    "key": obj["Key"],
                    "filename": obj["Key"].split("/")[-1],
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"].isoformat(),
                })
        return result
    except ClientError:
        return []


def move_file(src_key: str, dst_key: str) -> None:
    """Przenosi plik w S3 (copy + delete)."""
    cfg = get_settings()
    client = _client()
    client.copy_object(
        Bucket=cfg.s3_bucket,
        CopySource={"Bucket": cfg.s3_bucket, "Key": src_key},
        Key=dst_key,
    )
    client.delete_object(Bucket=cfg.s3_bucket, Key=src_key)


def delete_file(key: str) -> None:
    cfg = get_settings()
    client = _client()
    client.delete_object(Bucket=cfg.s3_bucket, Key=key)
