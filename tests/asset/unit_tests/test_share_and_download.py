import unittest

from asset.application.ports.inbound.create_share_link import CreateShareLinkCommand
from asset.application.ports.inbound.download_asset import DownloadAssetCommand, DownloadSharedAssetQuery
from asset.application.ports.inbound.get_shared_asset import GetSharedAssetQuery
from asset.application.ports.outbound.storage.download import StorageDownloadResult
from asset.application.services.create_share_link_service import CreateShareLinkService
from asset.application.services.download_asset_service import DownloadAssetService, DownloadSharedAssetService
from asset.application.services.get_shared_asset_service import GetSharedAssetService
from asset.domain.aggregates.asset import Asset, AssetType
from asset.domain.value_objects.storage_url import StorageUrl
from shared.asset_category import AssetCategory
from shared.exceptions import AuthorizationException, InvalidStateException


class _UserVerification:
    def is_active_user(self, user_id: str) -> bool:
        return user_id == "user-1"


class _AssetRepository:
    def __init__(self, asset: Asset):
        self.asset = asset
        self.updated = False

    def find_by_id(self, asset_id: str) -> Asset:
        return self.asset

    def find_by_share_token(self, share_token: str) -> Asset:
        if self.asset.share_token != share_token:
            raise AssertionError("unexpected share token")
        return self.asset

    def update(self, asset: Asset) -> None:
        self.updated = True
        self.asset = asset


class _Storage:
    def execute(self, command):
        return StorageDownloadResult(bytes=b"gif-data", content_type="image/gif")


def _result_asset() -> Asset:
    return Asset(
        id="asset-1",
        user_id="user-1",
        asset_type=AssetType.ANIMATED,
        category=AssetCategory.COMPOSITION_RESULT,
        storage_url=StorageUrl("https://assets.example/result.gif"),
    )


class ShareAndDownloadServiceTest(unittest.TestCase):
    def test_share_link_is_created_once_and_resolves_to_result(self):
        repository = _AssetRepository(_result_asset())
        share_service = CreateShareLinkService(_UserVerification(), repository)

        first = share_service.execute(CreateShareLinkCommand(user_id="user-1", asset_id="asset-1"))
        second = share_service.execute(CreateShareLinkCommand(user_id="user-1", asset_id="asset-1"))
        shared = GetSharedAssetService(repository).execute(GetSharedAssetQuery(first.share_token))

        self.assertTrue(repository.updated)
        self.assertEqual(first.share_token, second.share_token)
        self.assertEqual(shared.asset_id, "asset-1")
        self.assertEqual(shared.result_url, "https://assets.example/result.gif")

    def test_download_requires_the_owner_or_a_valid_share_token(self):
        repository = _AssetRepository(_result_asset())
        share_token = CreateShareLinkService(_UserVerification(), repository).execute(
            CreateShareLinkCommand(user_id="user-1", asset_id="asset-1")
        ).share_token

        owner_download = DownloadAssetService(_UserVerification(), repository, _Storage()).execute(
            DownloadAssetCommand(user_id="user-1", asset_id="asset-1")
        )
        public_download = DownloadSharedAssetService(repository, _Storage()).execute(
            DownloadSharedAssetQuery(share_token)
        )

        self.assertEqual(owner_download.data, b"gif-data")
        self.assertEqual(public_download.data, b"gif-data")
        with self.assertRaises(AuthorizationException):
            DownloadAssetService(_UserVerification(), repository, _Storage()).execute(
                DownloadAssetCommand(user_id="user-2", asset_id="asset-1")
            )

    def test_only_composition_results_can_be_shared(self):
        asset = _result_asset()
        asset.category = AssetCategory.USER_UPLOAD
        repository = _AssetRepository(asset)

        with self.assertRaises(InvalidStateException):
            CreateShareLinkService(_UserVerification(), repository).execute(
                CreateShareLinkCommand(user_id="user-1", asset_id="asset-1")
            )
