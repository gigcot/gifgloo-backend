import os

import aioboto3

from composition.application.ports.outbound.aws.storage_port import StoragePort, StorageCategory
from shared.r2_config import private_bucket_name

_CATEGORY_CONFIG = {
    StorageCategory.TARGET: {"extension": "png", "content_type": "image/png"},
    StorageCategory.DRAFT: {"extension": "png", "content_type": "image/png"},
    StorageCategory.RESULT: {"extension": "gif", "content_type": "image/gif", "content_disposition": "attachment"},
}

BUCKET_NAME = os.getenv("R2_BUCKET_NAME")


class R2StorageAdapter(StoragePort):
    def make_key(self, job_id: str, category: StorageCategory) -> str:
        config = _CATEGORY_CONFIG[category]
        return f"compositions/{job_id}/{category.value}.{config['extension']}"

    def location_for(self, key: str, category: StorageCategory) -> str:
        if category == StorageCategory.RESULT:
            return f"{os.environ['R2_PUBLIC_URL'].rstrip('/')}/{key}"
        return f"r2://{private_bucket_name()}/{key}"

    async def upload(self, job_id: str, category: StorageCategory, data: bytes) -> str:
        config = _CATEGORY_CONFIG[category]
        key = self.make_key(job_id, category)
        extra = {}
        if "content_disposition" in config:
            extra["ContentDisposition"] = config["content_disposition"]
        if category != StorageCategory.RESULT:
            extra["CacheControl"] = "private, no-store"
        session = aioboto3.Session()
        async with session.client(
            "s3",
            endpoint_url=os.getenv("R2_ENDPOINT_URL"),
            aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
            region_name="auto",
        ) as client:
            await client.put_object(
                Bucket=BUCKET_NAME if category == StorageCategory.RESULT else private_bucket_name(),
                Key=key,
                Body=data,
                ContentType=config["content_type"],
                **extra,
            )
        return key
