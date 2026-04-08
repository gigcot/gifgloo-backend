import os

import boto3

from composition.application.ports.outbound.aws.storage_port import StoragePort, StorageCategory

_CATEGORY_CONFIG = {
    StorageCategory.TARGET: {"extension": "png", "content_type": "image/png"},
    StorageCategory.DRAFT: {"extension": "png", "content_type": "image/png"},
    StorageCategory.RESULT: {"extension": "gif", "content_type": "image/gif", "content_disposition": "attachment"},
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
    def make_key(self, job_id: str, category: StorageCategory) -> str:
        config = _CATEGORY_CONFIG[category]
        return f"compositions/{job_id}/{category.value}.{config['extension']}"

    def public_url_for(self, key: str) -> str:
        return f"{os.getenv('R2_PUBLIC_URL')}/{key}"

    async def upload(self, job_id: str, category: StorageCategory, data: bytes) -> str:
        config = _CATEGORY_CONFIG[category]
        key = self.make_key(job_id, category)
        extra = {}
        if "content_disposition" in config:
            extra["ContentDisposition"] = config["content_disposition"]
        _make_client().put_object(
            Bucket=BUCKET_NAME,
            Key=key,
            Body=data,
            ContentType=config["content_type"],
            **extra,
        )
        return key
