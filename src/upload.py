"""上传 mp3 到 Cloudflare R2(S3 兼容)。

环境变量未配置时跳过,自动 fallback 到本地路径,供阶段 1 本地开发用。
"""
from __future__ import annotations

import logging
from pathlib import Path

import boto3
from botocore.config import Config

from .config import R2

log = logging.getLogger(__name__)


def is_configured() -> bool:
    return all(
        [R2["account_id"], R2["access_key"], R2["secret_key"], R2["bucket"], R2["public_base"]]
    )


def _client():
    endpoint = f"https://{R2['account_id']}.r2.cloudflarestorage.com"
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=R2["access_key"],
        aws_secret_access_key=R2["secret_key"],
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def upload_mp3(local_path: Path, key: str) -> str:
    """上传到 R2,返回公开访问 URL。
    key: 对象名,如 'episodes/2026-05-26.mp3'
    """
    if not is_configured():
        log.info("R2 not configured, fallback to local path")
        return f"/audio/{local_path.name}"

    s3 = _client()
    log.info("uploading %s -> r2://%s/%s", local_path.name, R2["bucket"], key)
    s3.upload_file(
        str(local_path),
        R2["bucket"],
        key,
        ExtraArgs={
            "ContentType": "audio/mpeg",
            "CacheControl": "public, max-age=31536000, immutable",
        },
    )
    public_url = f"{R2['public_base'].rstrip('/')}/{key}"
    log.info("uploaded -> %s", public_url)
    return public_url
