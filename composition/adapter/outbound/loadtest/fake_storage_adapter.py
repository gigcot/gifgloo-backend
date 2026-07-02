import os

from composition.application.ports.outbound.aws.storage_port import StorageCategory, StoragePort


_CATEGORY_EXTENSION = {
    StorageCategory.TARGET: "png",
    StorageCategory.DRAFT: "png",
    StorageCategory.RESULT: "gif",
}


class FakeStorageAdapter(StoragePort):
    def __init__(self):
        self._public_url = os.environ["LOADTEST_STORAGE_PUBLIC_URL"]

    def make_key(self, job_id: str, category: StorageCategory) -> str:
        return f"compositions/{job_id}/{category.value}.{_CATEGORY_EXTENSION[category]}"

    def public_url_for(self, key: str) -> str:
        return f"{self._public_url.rstrip('/')}/{key}"

    async def upload(self, job_id: str, category: StorageCategory, data: bytes) -> str:
        return self.make_key(job_id, category)
