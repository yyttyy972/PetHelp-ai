import os
from pathlib import Path

from app.config import MEDIA_ROOT

_required = ["R2_ACCESS_KEY_ID", "R2_SECRET_ACCESS_KEY", "R2_BUCKET_NAME", "R2_ENDPOINT_URL"]
R2_ENABLED = all(os.getenv(name) for name in _required)

if R2_ENABLED:
    import boto3
    from botocore.exceptions import ClientError

    _bucket = os.environ["R2_BUCKET_NAME"]
    _client = boto3.client(
        "s3",
        endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
        region_name="auto",
    )


def put(key: str, data: bytes, content_type: str) -> None:
    if R2_ENABLED:
        _client.put_object(Bucket=_bucket, Key=key, Body=data, ContentType=content_type)
        return
    path = MEDIA_ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def exists(key: str) -> bool:
    if R2_ENABLED:
        try:
            _client.head_object(Bucket=_bucket, Key=key)
            return True
        except ClientError:
            return False
    return (MEDIA_ROOT / key).is_file()


def get(key: str) -> tuple[bytes, str]:
    if R2_ENABLED:
        response = _client.get_object(Bucket=_bucket, Key=key)
        return response["Body"].read(), response.get("ContentType") or "application/octet-stream"
    path = MEDIA_ROOT / key
    return path.read_bytes(), "application/octet-stream"
