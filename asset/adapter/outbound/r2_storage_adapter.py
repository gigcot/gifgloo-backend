import os
import boto3

from asset.application.ports.outbound.storage.upload import StorageUploadCommand, StorageUploadPort, StorageUploadResult
from asset.application.ports.outbound.storage.download import StorageDownloadCommand, StorageDownloadPort, StorageDownloadResult


def _make_client():
    return boto3.client(
        "s3",
        endpoint_url=os.getenv("R2_ENDPOINT_URL"),
        aws_access_key_id=os.getenv("R2_ACCESS_KEY_ID"),
        aws_secret_access_key=os.getenv("R2_SECRET_ACCESS_KEY"),
        region_name="auto",
    )


BUCKET_NAME = os.getenv("R2_BUCKET_NAME")


class R2UploadAdapter(StorageUploadPort):
    def execute(self, command: StorageUploadCommand) -> StorageUploadResult:
        client = _make_client()
        key = f"{command.asset_type.value}/{command.asset_id}"
        client.put_object(Bucket=BUCKET_NAME, Key=key, Body=command.image_data)
        url = f"{os.getenv('R2_PUBLIC_URL')}/{key}"
        return StorageUploadResult(storage_url=url)


class R2DownloadAdapter(StorageDownloadPort):
    def execute(self, command: StorageDownloadCommand) -> StorageDownloadResult:
        client = _make_client()
        key = command.storage_url.split(f"{os.getenv('R2_PUBLIC_URL')}/")[-1]
        response = client.get_object(Bucket=BUCKET_NAME, Key=key)
        return StorageDownloadResult(bytes=response["Body"].read())
