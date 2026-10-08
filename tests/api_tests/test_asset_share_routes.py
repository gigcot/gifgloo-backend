import os
import unittest

import jwt
from fastapi import FastAPI
from fastapi.testclient import TestClient

os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-with-at-least-32-bytes")
os.environ.setdefault("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("ASYNC_DATABASE_URL", "postgresql+asyncpg://postgres:postgres@127.0.0.1:5432/gifgloo_test")
os.environ.setdefault("R2_BUCKET_NAME", "gifgloo-test")

from asset.adapter.inbound.fastapi.asset_router import router as asset_router  # noqa: E402
from asset.application.ports.inbound.create_share_link import CreateShareLinkResult  # noqa: E402
from asset.application.ports.inbound.download_asset import DownloadAssetResult  # noqa: E402
from asset.application.ports.inbound.get_shared_asset import GetSharedAssetResult  # noqa: E402
from config.asset import (  # noqa: E402
    get_create_share_link_service,
    get_download_asset_service,
    get_download_shared_asset_service,
    get_shared_asset_service,
)


class _CreateShareLinkService:
    def execute(self, command):
        self.command = command
        return CreateShareLinkResult(share_token="share-token")


class _GetSharedAssetService:
    def execute(self, query):
        self.query = query
        return GetSharedAssetResult(asset_id="asset-1", result_url="https://assets.example/result.gif")


class _DownloadAssetService:
    def execute(self, command):
        self.command = command
        return DownloadAssetResult(data=b"gif-data", content_type="image/gif")


class AssetShareRoutesTest(unittest.TestCase):
    def setUp(self):
        self.share_service = _CreateShareLinkService()
        self.shared_asset_service = _GetSharedAssetService()
        self.download_service = _DownloadAssetService()
        self.shared_download_service = _DownloadAssetService()
        app = FastAPI()
        app.include_router(asset_router)
        app.dependency_overrides[get_create_share_link_service] = lambda: self.share_service
        app.dependency_overrides[get_shared_asset_service] = lambda: self.shared_asset_service
        app.dependency_overrides[get_download_asset_service] = lambda: self.download_service
        app.dependency_overrides[get_download_shared_asset_service] = lambda: self.shared_download_service
        self.client = TestClient(app)

    def _set_auth_cookie(self):
        token = jwt.encode({"user_id": "user-1"}, os.environ["JWT_SECRET_KEY"], algorithm="HS256")
        self.client.cookies.set("user_token", token)

    def test_owner_can_create_share_link_and_download_file(self):
        self._set_auth_cookie()

        share_response = self.client.post("/assets/asset-1/share")
        download_response = self.client.get("/assets/asset-1/download")

        self.assertEqual(share_response.json(), {"share_token": "share-token"})
        self.assertEqual(self.share_service.command.user_id, "user-1")
        self.assertEqual(download_response.content, b"gif-data")
        self.assertEqual(download_response.headers["content-disposition"], 'attachment; filename="gifgloo-asset-1.gif"')

    def test_shared_result_is_public_and_downloadable(self):
        result_response = self.client.get("/assets/shared/share-token")
        download_response = self.client.get("/assets/shared/share-token/download")

        self.assertEqual(
            result_response.json(),
            {"asset_id": "asset-1", "result_url": "https://assets.example/result.gif"},
        )
        self.assertEqual(self.shared_asset_service.query.share_token, "share-token")
        self.assertEqual(download_response.content, b"gif-data")
        self.assertEqual(download_response.headers["content-disposition"], 'attachment; filename="gifgloo.gif"')
