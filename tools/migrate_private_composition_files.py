"""Inventory, copy and verify private composition files without deleting sources."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re

import boto3
from botocore.exceptions import ClientError

from shared.exceptions import InvalidStateException, ValidationException
from shared.r2_config import private_bucket_name


UUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
PRIVATE_KEY = re.compile(
    rf"(?:compositions/{UUID}/(?:target|draft)\.png|"
    rf"temp/{UUID}/(?:frame|composited)_\d+\.png|STATIC/{UUID})"
)


def inventory(client, public_bucket: str, private_bucket: str) -> dict:
    files = []
    unclassified = []
    for prefix in ("compositions/", "temp/", "STATIC/"):
        for page in client.get_paginator("list_objects_v2").paginate(Bucket=public_bucket, Prefix=prefix):
            if "Contents" not in page:
                continue
            for item in page["Contents"]:
                key = item["Key"]
                if PRIVATE_KEY.fullmatch(key):
                    files.append({"key": key, "size": item["Size"], "etag": item["ETag"]})
                elif not re.fullmatch(rf"compositions/{UUID}/result\.gif", key):
                    unclassified.append(key)
    return {"public_bucket": public_bucket, "private_bucket": private_bucket, "files": files, "unclassified_keys": unclassified}


def validate_manifest(manifest: dict, public_bucket: str, private_bucket: str) -> None:
    if not private_bucket or public_bucket == private_bucket:
        raise ValidationException("서로 다른 공개·비공개 버킷이 필요합니다")
    if manifest["public_bucket"] != public_bucket or manifest["private_bucket"] != private_bucket:
        raise ValidationException("목록의 버킷과 현재 설정이 다릅니다")
    keys = set()
    for item in manifest["files"]:
        key = item["key"]
        if not PRIVATE_KEY.fullmatch(key) or key in keys:
            raise ValidationException("비공개 전환 대상이 아니거나 중복된 객체 키입니다")
        if type(item["size"]) is not int or item["size"] < 0 or not item["etag"]:
            raise ValidationException("객체의 크기·ETag가 필요합니다")
        keys.add(key)


def content_digest(client, bucket: str, key: str) -> tuple[str, int]:
    response = client.get_object(Bucket=bucket, Key=key)
    body = response["Body"]
    digest = hashlib.sha256()
    size = 0
    try:
        while chunk := body.read(1024 * 1024):
            digest.update(chunk)
            size += len(chunk)
    finally:
        body.close()
    return digest.hexdigest(), size


def copy_and_verify(client, manifest: dict, *, copy: bool) -> int:
    source = manifest["public_bucket"]
    destination = manifest["private_bucket"]
    validate_manifest(manifest, source, destination)
    verified = 0
    for item in manifest["files"]:
        key = item["key"]
        source_head = client.head_object(Bucket=source, Key=key)
        if source_head["ETag"] != item["etag"] or source_head["ContentLength"] != item["size"]:
            raise InvalidStateException(f"목록 작성 후 원본이 변경됐습니다: {key}")
        try:
            client.head_object(Bucket=destination, Key=key)
        except ClientError as exc:
            if exc.response["Error"]["Code"] not in {"404", "NoSuchKey", "NotFound"}:
                raise
            if not copy:
                raise InvalidStateException(f"비공개 복사본이 없습니다: {key}") from exc
            client.copy_object(
                Bucket=destination, Key=key,
                CopySource={"Bucket": source, "Key": key},
                CopySourceIfMatch=item["etag"],
                MetadataDirective="REPLACE", ContentType=source_head["ContentType"],
                CacheControl="private, no-store",
                **({"Metadata": source_head["Metadata"]} if "Metadata" in source_head else {}),
            )
        if content_digest(client, source, key) != content_digest(client, destination, key):
            raise InvalidStateException(f"복사본 내용이 원본과 다릅니다: {key}")
        after = client.head_object(Bucket=source, Key=key)
        if after["ETag"] != item["etag"] or after["ContentLength"] != item["size"]:
            raise InvalidStateException(f"검증 도중 원본이 변경됐습니다: {key}")
        verified += 1
    return verified


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("plan", "copy", "verify"))
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    public_bucket = os.environ["R2_BUCKET_NAME"]
    private_bucket = private_bucket_name()
    client = boto3.client(
        "s3", endpoint_url=os.environ["R2_ENDPOINT_URL"],
        aws_access_key_id=os.environ["R2_ACCESS_KEY_ID"],
        aws_secret_access_key=os.environ["R2_SECRET_ACCESS_KEY"], region_name="auto",
    )
    if args.action == "plan":
        manifest = inventory(client, public_bucket, private_bucket)
        with args.manifest.open("x", encoding="utf-8") as file:
            os.chmod(args.manifest, 0o600)
            json.dump(manifest, file, ensure_ascii=False, indent=2)
        print(f"대상 {len(manifest['files'])}개, 미분류 {len(manifest['unclassified_keys'])}개. 저장소 변경 없음.")
        return
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    validate_manifest(manifest, public_bucket, private_bucket)
    count = copy_and_verify(client, manifest, copy=args.action == "copy")
    print(f"{count}개 내용 검증 완료. 공개 원본 삭제·CDN 캐시 제거는 실행하지 않았습니다.")


if __name__ == "__main__":
    main()
