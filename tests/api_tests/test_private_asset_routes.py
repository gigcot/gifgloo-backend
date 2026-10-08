import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")

from asset.adapter.inbound.fastapi.asset_router import router as asset_router
from asset.application.ports.outbound.storage.download import StorageDownloadResult
from asset.application.services.download_asset_service import DownloadAssetService
from asset.domain.aggregates.asset import Asset, AssetStatus, AssetType
from asset.domain.value_objects.storage_url import StorageUrl
from composition.adapter.inbound.fastapi.composition_router import router as composition_router
from composition.application.services.get_composition_list_service import GetCompositionListService
from composition.domain.aggregates.composition_job import CompositionJob
from config.asset import get_download_asset_service, get_asset_list_service
from config.composition import get_composition_list_service
from shared.asset_category import AssetCategory
from shared.exceptions import AuthenticationException
from shared.fastapi_error_handler import register_error_handlers
from user.adapter.inbound.fastapi.session_middleware import UserSessionMiddleware


class PrivateAssetRoutesTest(unittest.TestCase):
    def setUp(self):
        self.asset = Asset("photo", "owner", AssetType.STATIC, AssetCategory.USER_UPLOAD, StorageUrl("r2://private-inputs/compositions/job/target.png"))
        self.repo = Mock()
        self.repo.find_by_id.return_value = self.asset
        self.users = Mock()
        self.users.is_active_user.return_value = True
        self.storage = Mock()
        self.storage.execute.return_value = StorageDownloadResult(b"private-png", "image/png")
        service = DownloadAssetService(self.users, self.repo, self.storage)
        app = FastAPI()
        app.include_router(asset_router)
        app.include_router(composition_router)
        register_error_handlers(app)
        app.add_middleware(UserSessionMiddleware)
        app.dependency_overrides[get_download_asset_service] = lambda: service
        job = CompositionJob("owner")
        job.target_asset_id = "photo"
        job.target_url = "https://cdn.example/compositions/job/target.png"
        jobs = AsyncMock()
        jobs.find_all_by_user_id.return_value = [job]
        app.dependency_overrides[get_composition_list_service] = lambda: GetCompositionListService(jobs)
        listing = AsyncMock()
        listing.execute.return_value = SimpleNamespace(assets=[SimpleNamespace(asset_id="photo", asset_type=AssetType.STATIC, category=AssetCategory.USER_UPLOAD, url=job.target_url)])
        app.dependency_overrides[get_asset_list_service] = lambda: listing
        self.session_verification = AsyncMock(return_value=SimpleNamespace(user_kind="anonymous", consent_required=False))
        for target, replacement in [
            ("user.adapter.inbound.fastapi.session_middleware.AsyncSessionLocal", Mock(return_value=AsyncMock())),
            ("user.adapter.inbound.fastapi.session_middleware.VerifySessionService.execute", self.session_verification),
        ]:
            mocked = patch(target, replacement)
            mocked.start()
            self.addCleanup(mocked.stop)
        self.client = TestClient(app)

    def sign_in(self, user_id="owner", user_kind="anonymous"):
        token = jwt.encode({"user_id": user_id, "user_kind": user_kind, "session_version": 1, "purpose": "user_session"}, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
        self.client.cookies.set("user_token", token)

    def test_anonymous_and_member_owners_can_view_without_public_caching(self):
        for kind in ("anonymous", "member"):
            with self.subTest(kind=kind):
                self.sign_in(user_kind=kind)
                self.session_verification.return_value.user_kind = kind
                response = self.client.get("/assets/photo/content")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.content, b"private-png")
                self.assertEqual(response.headers["content-type"], "image/png")
                self.assertEqual(response.headers["cache-control"], "private, no-store")
                self.assertEqual(response.headers["vary"], "Cookie")
                self.assertEqual(response.headers["x-content-type-options"], "nosniff")

    def test_no_session_cannot_read_photo(self):
        self.assertEqual(self.client.get("/assets/photo/content").status_code, 401)
        self.storage.execute.assert_not_called()

    def test_other_active_user_cannot_read_photo(self):
        self.sign_in("other")
        self.assertEqual(self.client.get("/assets/photo/content").status_code, 403)
        self.storage.execute.assert_not_called()

    def test_revoked_session_cannot_read_photo(self):
        self.sign_in()
        self.session_verification.side_effect = AuthenticationException("expired")
        self.assertEqual(self.client.get("/assets/photo/content").status_code, 401)
        self.storage.execute.assert_not_called()

    def test_deleted_photo_cannot_be_viewed_or_downloaded(self):
        self.sign_in()
        self.asset.status = AssetStatus.DELETED
        for action in ("content", "download"):
            self.assertEqual(self.client.get(f"/assets/photo/{action}").status_code, 404)
        self.storage.execute.assert_not_called()

    def test_lists_expose_authenticated_endpoint_instead_of_storage_location(self):
        self.sign_in()
        jobs = self.client.get("/compositions")
        self.assertEqual(jobs.status_code, 200)
        self.assertEqual(jobs.json()["jobs"][0]["target_asset_id"], "photo")
        self.assertEqual(jobs.json()["jobs"][0]["target_url"], "http://testserver/assets/photo/content")
        assets = self.client.get("/assets")
        self.assertEqual(assets.json()["assets"][0]["url"], "http://testserver/assets/photo/content")
        for response in (jobs, assets):
            self.assertNotIn("target.png", response.text)
            self.assertNotIn("private-inputs", response.text)
            self.assertNotIn("cdn.example", response.text)
