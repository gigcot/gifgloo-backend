import os

import boto3

from composition.application.ports.outbound.aws.storage_port import StoragePort

_CATEGORY_CONFIG = {
    "target": {"extension": "png", "content_type": "image/png"},
    "draft": {"extension": "png", "content_type": "image/png"},
    "result": {"extension": "gif", "content_type": "image/gif"},
}


def _make_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


BUCKET_NAME = os.getenv("R2_BUCKET_NAME", "gifgloo")


class R2StorageAdapter(StoragePort):
    async def upload(self, job_id: str, category: str, data: bytes) -> str:
        config = _CATEGORY_CONFIG.get(category, {"extension": "bin", "content_type": "application/octet-stream"})
        key = f"compositions/{job_id}/{category}.{config['extension']}"

        client = _make_client()
        client.put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=config["content_type"],
        )
        return f"{os.getenv('R2_PUBLIC_URL')}/{key}"
