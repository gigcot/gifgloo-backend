import os
import boto3
from botocore.exceptions import ClientError

from asset.application.ports.outbound.storage.upload import StorageUploadCommand, StorageUploadPort, StorageUploadResult
from asset.application.ports.outbound.storage.download import StorageDownloadCommand, StorageDownloadPort, StorageDownloadResult
from asset.domain.aggregates.asset import AssetType
from shared.asset_category import AssetCategory
from shared.exceptions import NotFoundException, ValidationException
from shared.r2_config import private_bucket_name


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
        private = command.asset_type == AssetType.STATIC
        bucket = private_bucket_name() if private else BUCKET_NAME
        client.put_object(
            Bucket=bucket, Key=key, Body=command.image_data,
            **({"CacheControl": "private, no-store"} if private else {}),
        )
        url = f"r2://{bucket}/{key}" if private else f"{os.environ['R2_PUBLIC_URL'].rstrip('/')}/{key}"
        return StorageUploadResult(storage_url=url)


class R2DownloadAdapter(StorageDownloadPort):
    def execute(self, command: StorageDownloadCommand) -> StorageDownloadResult:
        client = _make_client()
        private = command.category in {AssetCategory.USER_UPLOAD, AssetCategory.COMPOSITION_DRAFT}
        bucket = private_bucket_name() if private else BUCKET_NAME
        public_prefix = f"{os.environ['R2_PUBLIC_URL'].rstrip('/')}/"
        private_prefix = f"r2://{bucket}/"
        if private and command.storage_url.startswith(private_prefix):
            key = command.storage_url[len(private_prefix):]
        elif command.storage_url.startswith(public_prefix):
            key = command.storage_url[len(public_prefix):]
        else:
            raise ValidationException("지원하지 않는 파일 저장 위치입니다")
        try:
            response = client.get_object(Bucket=bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                raise NotFoundException("파일을 찾을 수 없습니다") from exc
            raise
        body = response["Body"]
        try:
            return StorageDownloadResult(
                bytes=body.read(), content_type=response["ContentType"],
            )
        finally:
            body.close()
