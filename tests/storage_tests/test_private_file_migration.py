import hashlib
import io
import unittest

from botocore.exceptions import ClientError

from shared.exceptions import InvalidStateException, ValidationException
from tools.migrate_private_composition_files import copy_and_verify, inventory, validate_manifest


JOB = "11111111-1111-4111-8111-111111111111"
TARGET = f"compositions/{JOB}/target.png"
RESULT = f"compositions/{JOB}/result.gif"


class MemoryR2:
    def __init__(self):
        self.objects = {("public", TARGET): b"private-photo", ("public", RESULT): b"public-gif"}
        self.copies = []

    def get_paginator(self, operation):
        assert operation == "list_objects_v2"
        return self

    def paginate(self, Bucket, Prefix):
        contents = [{"Key": key, "Size": len(data), "ETag": hashlib.sha256(data).hexdigest()} for (bucket, key), data in self.objects.items() if bucket == Bucket and key.startswith(Prefix)]
        return [{"Contents": contents}] if contents else [{}]

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError({"Error": {"Code": "NoSuchKey"}}, "HeadObject")
        data = self.objects[Bucket, Key]
        return {"ETag": hashlib.sha256(data).hexdigest(), "ContentLength": len(data), "ContentType": "image/png"}

    def get_object(self, Bucket, Key):
        return {"Body": io.BytesIO(self.objects[Bucket, Key])}

    def copy_object(self, **kwargs):
        source = kwargs["CopySource"]
        assert self.head_object(source["Bucket"], source["Key"])["ETag"] == kwargs["CopySourceIfMatch"]
        self.objects[kwargs["Bucket"], kwargs["Key"]] = self.objects[source["Bucket"], source["Key"]]
        self.copies.append(kwargs)


class PrivateMigrationTest(unittest.TestCase):
    def setUp(self):
        self.client = MemoryR2()

    def test_plan_excludes_results_and_reports_unknown_keys(self):
        self.client.objects["public", f"compositions/{JOB}/unknown.png"] = b"unknown"
        plan = inventory(self.client, "public", "private")
        self.assertEqual([item["key"] for item in plan["files"]], [TARGET])
        self.assertEqual(plan["unclassified_keys"], [f"compositions/{JOB}/unknown.png"])
        self.assertEqual(self.client.copies, [])

    def test_copy_preserves_sources_and_result_then_can_be_verified_again(self):
        plan = inventory(self.client, "public", "private")
        self.assertEqual(copy_and_verify(self.client, plan, copy=True), 1)
        self.assertEqual(self.client.objects["private", TARGET], b"private-photo")
        self.assertEqual(self.client.objects["public", TARGET], b"private-photo")
        self.assertEqual(self.client.objects["public", RESULT], b"public-gif")
        self.assertNotIn(("private", RESULT), self.client.objects)
        self.assertEqual(copy_and_verify(self.client, plan, copy=False), 1)
        self.assertEqual(len(self.client.copies), 1)
        self.assertEqual(self.client.copies[0]["CacheControl"], "private, no-store")

    def test_changed_source_stops_before_copy(self):
        plan = inventory(self.client, "public", "private")
        self.client.objects["public", TARGET] = b"new-photo"
        with self.assertRaises(InvalidStateException):
            copy_and_verify(self.client, plan, copy=True)
        self.assertEqual(self.client.copies, [])

    def test_existing_different_destination_is_not_overwritten(self):
        plan = inventory(self.client, "public", "private")
        self.client.objects["private", TARGET] = b"different-photo"
        with self.assertRaises(InvalidStateException):
            copy_and_verify(self.client, plan, copy=True)
        self.assertEqual(self.client.objects["private", TARGET], b"different-photo")
        self.assertEqual(self.client.copies, [])

    def test_result_keys_and_wrong_bucket_and_duplicates_are_rejected(self):
        for alteration in ("result", "bucket", "duplicate"):
            plan = inventory(self.client, "public", "private")
            if alteration == "result":
                plan["files"][0]["key"] = RESULT
            elif alteration == "bucket":
                plan["private_bucket"] = "unexpected"
            else:
                plan["files"].append(plan["files"][0])
            with self.assertRaises(ValidationException):
                validate_manifest(plan, "public", "private")

    def test_verification_without_copy_rejects_missing_destination(self):
        with self.assertRaises(InvalidStateException):
            copy_and_verify(self.client, inventory(self.client, "public", "private"), copy=False)
        self.assertEqual(self.client.copies, [])
