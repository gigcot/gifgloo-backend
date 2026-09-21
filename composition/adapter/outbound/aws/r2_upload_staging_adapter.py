import hashlib
import os
import uuid

import aioboto3
from botocore.exceptions import ClientError

from composition.application.ports.outbound.aws.upload_staging_port import (
    PrepareUploadCommand,
    PrepareUploadResult,
    ResolveUploadCommand,
    UploadStagingPort,
)
from composition.domain.value_objects.composition_policy import (
    ALLOWED_TARGET_CONTENT_TYPES,
    MAX_TARGET_UPLOAD_BYTES,
)
from shared.exceptions import NotFoundException, PayloadTooLargeException, ValidationException


UPLOAD_URL_TTL_SECONDS = 600


class R2UploadStagingAdapter(UploadStagingPort):
    def __init__(self):
        self._bucket = os.environ["R2_UPLOAD_BUCKET_NAME"]

    def _key(self, user_id: str, upload_id: str) -> str:
        owner = hashlib.sha256(user_id.encode()).hexdigest()
        return f"composition-uploads/{owner}/{upload_id}"

    def _client(self):
        return aioboto3.Session().client(
            "s3",
            endpoint_url=os.environ["R2_ENDPOINT_URL"],
            aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
        )

    async def prepare(self, command: PrepareUploadCommand) -> PrepareUploadResult:
        if command.content_type not in ALLOWED_TARGET_CONTENT_TYPES:
            raise ValidationException("지원하지 않는 이미지 형식입니다")
        if command.size < 1:
            raise ValidationException("빈 이미지 파일은 업로드할 수 없습니다")
        if command.size > MAX_TARGET_UPLOAD_BYTES:
            raise PayloadTooLargeException("이미지는 최대 15MB까지 업로드할 수 있습니다")

        upload_id = str(uuid.uuid4())
        key = self._key(command.user_id, upload_id)
        async with self._client() as client:
            upload_url = await client.generate_presigned_url(
                "put_object",
                Params={"Bucket": self._bucket, "Key": key, "ContentType": command.content_type},
                ExpiresIn=UPLOAD_URL_TTL_SECONDS,
            )
        return PrepareUploadResult(
            upload_id=upload_id,
            upload_url=upload_url,
            headers={"Content-Type": command.content_type},
            expires_in_seconds=UPLOAD_URL_TTL_SECONDS,
        )

    async def resolve(self, command: ResolveUploadCommand) -> str:
        try:
            uuid.UUID(command.upload_id)
        except ValueError as exc:
            raise ValidationException("업로드 ID가 올바르지 않습니다") from exc

        key = self._key(command.user_id, command.upload_id)
        try:
            async with self._client() as client:
                metadata = await client.head_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] in {"404", "NoSuchKey", "NotFound"}:
                raise NotFoundException("업로드한 이미지를 찾을 수 없습니다") from exc
            raise

        size = metadata["ContentLength"]
        if size < 1:
            raise ValidationException("빈 이미지 파일은 사용할 수 없습니다")
        if size > MAX_TARGET_UPLOAD_BYTES:
            raise PayloadTooLargeException("이미지는 최대 15MB까지 업로드할 수 있습니다")
        if metadata["ContentType"] not in ALLOWED_TARGET_CONTENT_TYPES:
            raise ValidationException("지원하지 않는 이미지 형식입니다")
        return key
