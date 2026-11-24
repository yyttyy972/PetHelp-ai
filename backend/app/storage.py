import os
from pathlib import Path

from app.config import MEDIA_ROOT

_access_key = os.getenv("AWS_ACCESS_KEY_ID") or os.getenv("R2_ACCESS_KEY_ID")
_secret_key = os.getenv("AWS_SECRET_ACCESS_KEY") or os.getenv("R2_SECRET_ACCESS_KEY")
_bucket = os.getenv("S3_BUCKET_NAME") or os.getenv("R2_BUCKET_NAME")
_endpoint = os.getenv("AWS_ENDPOINT_URL_S3") or os.getenv("R2_ENDPOINT_URL")
S3_ENABLED = all((_access_key, _secret_key, _bucket, _endpoint))

if S3_ENABLED:
    import boto3
    from botocore.config import Config
    from botocore.exceptions import ClientError

    _client = boto3.client(
        "s3",
        endpoint_url=_endpoint,
        aws_access_key_id=_access_key,
        aws_secret_access_key=_secret_key,
        region_name=os.getenv("AWS_REGION", "auto"),
        config=Config(s3={"addressing_style": "path"}),
    )


def put(key: str, data: bytes, content_type: str) -> None:
    if S3_ENABLED:
        _client.put_object(Bucket=_bucket, Key=key, Body=data, ContentType=content_type)
        return
    path = MEDIA_ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def exists(key: str) -> bool:
    if S3_ENABLED:
        try:
            _client.head_object(Bucket=_bucket, Key=key)
            return True
        except ClientError:
            return False
    return (MEDIA_ROOT / key).is_file()


def get(key: str) -> tuple[bytes, str]:
    if S3_ENABLED:
        response = _client.get_object(Bucket=_bucket, Key=key)
        return response["Body"].read(), response.get("ContentType") or "application/octet-stream"
    path = MEDIA_ROOT / key
    return path.read_bytes(), "application/octet-stream"
