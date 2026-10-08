import importlib.util
import io
import os
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

from botocore.exceptions import ClientError
from PIL import Image

from asset.adapter.outbound import r2_storage_adapter as asset_storage
from asset.application.ports.outbound.storage.download import StorageDownloadCommand
from composition.adapter.outbound.aws import r2_storage_adapter as composition_storage
from composition.application.ports.outbound.aws.storage_port import StorageCategory
from shared.asset_category import AssetCategory
from shared.exceptions import ExternalServiceException, NotFoundException, ValidationException
from shared.r2_config import private_bucket_name


ENV = {
    "R2_BUCKET_NAME": "public-results", "R2_PRIVATE_BUCKET_NAME": "private-inputs",
    "R2_UPLOAD_BUCKET_NAME": "staging", "R2_PUBLIC_URL": "https://cdn.example",
    "OPENAI_API_KEY": "test-not-a-real-key",
}
ROOT = Path(__file__).resolve().parents[2]


class PrivateStorageTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.env = patch.dict(os.environ, ENV)
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_private_bucket_cannot_be_missing_or_the_public_bucket(self):
        with patch.dict(os.environ, {"R2_PRIVATE_BUCKET_NAME": "public-results"}):
            with self.assertRaises(ExternalServiceException):
                private_bucket_name()
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(KeyError):
                private_bucket_name()

    async def test_target_and_draft_uploads_are_private_but_result_stays_public(self):
        client = AsyncMock()
        context = Mock()
        context.__aenter__ = AsyncMock(return_value=client)
        context.__aexit__ = AsyncMock(return_value=False)
        session = Mock()
        session.client.return_value = context
        with patch.object(composition_storage.aioboto3, "Session", return_value=session), patch.object(composition_storage, "BUCKET_NAME", "public-results"):
            adapter = composition_storage.R2StorageAdapter()
            for category in StorageCategory:
                with self.subTest(category=category):
                    key = await adapter.upload("job", category, b"image")
                    expected = "public-results" if category == StorageCategory.RESULT else "private-inputs"
                    self.assertEqual(client.put_object.call_args.kwargs["Bucket"], expected)
                    location = adapter.location_for(key, category)
                    self.assertTrue(location.startswith("https://cdn.example/" if category == StorageCategory.RESULT else "r2://private-inputs/"))

    def test_legacy_and_new_private_locations_read_only_from_private_bucket(self):
        client = Mock()
        for category, filename in [(AssetCategory.USER_UPLOAD, "target.png"), (AssetCategory.COMPOSITION_DRAFT, "draft.png")]:
            for prefix in ("https://cdn.example/", "r2://private-inputs/"):
                body = io.BytesIO(b"png")
                client.get_object.return_value = {"Body": body, "ContentType": "image/png"}
                key = f"compositions/job/{filename}"
                with patch.object(asset_storage, "_make_client", return_value=client):
                    result = asset_storage.R2DownloadAdapter().execute(StorageDownloadCommand(prefix + key, category))
                self.assertEqual(result.bytes, b"png")
                self.assertEqual(result.content_type, "image/png")
                self.assertTrue(body.closed)
                client.get_object.assert_called_with(Bucket="private-inputs", Key=key)

    def test_missing_private_file_never_falls_back_to_public(self):
        client = Mock()
        client.get_object.side_effect = ClientError({"Error": {"Code": "NoSuchKey"}}, "GetObject")
        with patch.object(asset_storage, "_make_client", return_value=client):
            with self.assertRaises(NotFoundException):
                asset_storage.R2DownloadAdapter().execute(StorageDownloadCommand("https://cdn.example/compositions/job/target.png", AssetCategory.USER_UPLOAD))
        self.assertEqual(client.get_object.call_count, 1)
        self.assertEqual(client.get_object.call_args.kwargs["Bucket"], "private-inputs")

    def test_unrecognized_storage_host_is_rejected(self):
        client = Mock()
        with patch.object(asset_storage, "_make_client", return_value=client):
            with self.assertRaises(ValidationException):
                asset_storage.R2DownloadAdapter().execute(StorageDownloadCommand("https://cdn.example.attacker/target.png", AssetCategory.USER_UPLOAD))
        client.get_object.assert_not_called()

    def test_result_download_remains_in_public_bucket(self):
        client = Mock()
        client.get_object.return_value = {"Body": io.BytesIO(b"GIF89a"), "ContentType": "image/gif"}
        with patch.object(asset_storage, "_make_client", return_value=client), patch.object(asset_storage, "BUCKET_NAME", "public-results"):
            result = asset_storage.R2DownloadAdapter().execute(StorageDownloadCommand("https://cdn.example/compositions/job/result.gif", AssetCategory.COMPOSITION_RESULT))
        client.get_object.assert_called_once_with(Bucket="public-results", Key="compositions/job/result.gif")
        self.assertEqual(result.bytes, b"GIF89a")


class LambdaPrivateStorageTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, ENV):
            for name in ("ai_processor", "gif_processor"):
                spec = importlib.util.spec_from_file_location(name, ROOT / "lambda" / name / "handler.py")
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                setattr(cls, name, module)
        out = io.BytesIO()
        Image.new("RGB", (2, 2), "blue").save(out, format="PNG")
        cls.png = out.getvalue()

    def test_normalization_reads_staging_and_writes_private_then_deletes_staging(self):
        client = Mock()
        client.get_object.return_value = {"Body": io.BytesIO(self.png)}
        self.ai_processor._normalize_target(client, "compositions/job/target.png", "composition-uploads/upload")
        client.get_object.assert_called_once_with(Bucket="staging", Key="composition-uploads/upload")
        self.assertEqual(client.put_object.call_args.kwargs["Bucket"], "private-inputs")
        self.assertEqual(client.put_object.call_args.kwargs["CacheControl"], "private, no-store")
        client.delete_object.assert_called_once_with(Bucket="staging", Key="composition-uploads/upload")

    def test_existing_target_and_draft_processing_use_private_bucket(self):
        client = Mock()
        client.get_object.return_value = {"Body": io.BytesIO(self.png)}
        self.ai_processor._normalize_target(client, "compositions/job/target.png", None)
        client.get_object.assert_called_once_with(Bucket="private-inputs", Key="compositions/job/target.png")
        client.delete_object.assert_not_called()
        for key in ("compositions/job/draft.png", "temp/job/composited_0000.png"):
            self.ai_processor._upload_png(client, key, self.png)
            self.assertEqual(client.put_object.call_args.kwargs["Bucket"], "private-inputs")

    def test_extract_frames_writes_only_to_private_bucket(self):
        client = Mock()

        def run(args, **kwargs):
            if args[0] == self.gif_processor.FFPROBE:
                return SimpleNamespace(stdout='{"packets": [{"duration_time": "0.1"}]}')
            Path(args[-1].replace("%04d", "0001")).write_bytes(self.png)

        with patch.object(self.gif_processor, "_r2_client", return_value=client), patch.object(self.gif_processor, "_fetch_url", return_value=b"gif"), patch.object(self.gif_processor, "_count_frames", return_value=1), patch.object(self.gif_processor.subprocess, "run", side_effect=run):
            result = self.gif_processor.extract_frames("https://gif.example/gif", 10, "job")
        self.assertEqual(result["frame_keys"], ["temp/job/frame_0000.png"])
        self.assertEqual(client.put_object.call_args.kwargs["Bucket"], "private-inputs")

    def test_build_gif_reads_private_frames_and_writes_public_result(self):
        client = Mock()
        client.get_object.side_effect = lambda **kwargs: {"Body": io.BytesIO(self.png)}

        def render(args, **kwargs):
            Path(args[-1]).write_bytes(b"GIF89a")

        with patch.object(self.gif_processor, "_r2_client", return_value=client), patch.object(self.gif_processor.subprocess, "run", side_effect=render):
            self.gif_processor.build_gif(["temp/job/composited_0000.png"], [100], "compositions/job/result.gif")
        client.get_object.assert_called_once_with(Bucket="private-inputs", Key="temp/job/composited_0000.png")
        self.assertEqual(client.put_object.call_args.kwargs["Bucket"], "public-results")
        self.assertEqual(client.put_object.call_args.kwargs["Key"], "compositions/job/result.gif")

    def test_resume_from_build_uses_existing_private_objects(self):
        ai = self.ai_processor
        event = {"job_id": "job", "gif_url": "https://gif.example/gif", "callback_url": "https://api.example", "resume_from": "BUILDING_GIF", "durations_ms": [100], "spec": {}, "max_frames": 10}
        with patch.object(ai, "_r2_client"), patch.object(ai, "_normalize_target") as normalize, patch.object(ai, "_checkpoint"), patch.object(ai, "_invoke_gif_processor") as invoke, patch.object(ai, "_complete") as complete, patch.object(ai, "_fail") as fail:
            ai.run_pipeline(event, "run")
        normalize.assert_called_once()
        self.assertIsNone(normalize.call_args.args[2])
        self.assertEqual(invoke.call_args.args[0]["frames_r2_keys"], ["temp/job/composited_0000.png"])
        complete.assert_called_once_with("https://api.example", "job", "run", "compositions/job/draft.png", "compositions/job/result.gif")
        fail.assert_not_called()
