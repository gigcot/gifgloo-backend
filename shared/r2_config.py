import os

from shared.exceptions import ExternalServiceException


def private_bucket_name() -> str:
    bucket = os.environ["R2_PRIVATE_BUCKET_NAME"]
    if not bucket or bucket == os.environ["R2_BUCKET_NAME"]:
        raise ExternalServiceException("비공개 R2 버킷을 공개 결과 버킷과 별도로 설정해야 합니다")
    return bucket
