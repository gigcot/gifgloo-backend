import unittest
from unittest.mock import AsyncMock, Mock

from asset.application.ports.inbound.create_share_link import CreateShareLinkCommand
from asset.application.ports.inbound.download_asset import DownloadAssetCommand
from asset.application.services.create_share_link_service import CreateShareLinkService
from asset.application.services.download_asset_service import DownloadAssetService
from asset.domain.aggregates.asset import Asset, AssetType
from asset.domain.value_objects.storage_url import StorageUrl
from credit_account.application.services.grant_experiment_reward_service import GrantExperimentRewardService
from credit_account.unit_tests.test_grant_experiment_reward_service import CreditRepository
from experiment.adapter.outbound.domain_bridges.credit_reward_adapter import CreditRewardAdapter
from experiment.adapter.outbound.domain_bridges.user_acquisition_adapter import UserAcquisitionAdapter
from experiment.application.services.submit_experiment_survey_service import SubmitExperimentSurveyService
from experiment.unit_tests.test_experiment_survey_services import Completion, Responses, Transaction, valid_command
from shared.asset_category import AssetCategory
from shared.exceptions import AuthorizationException
from user.application.services.get_user_acquisition_campaign_service import GetUserAcquisitionCampaignService
from user.unit_tests import test_anonymous_sessions as fixtures
from user.application.ports.inbound.anonymous_session import AnonymousSessionCommand
from user.domain.value_objects.acquisition import Acquisition


class AnonymousExistingWorkflowsTest(unittest.IsolatedAsyncioTestCase):
    async def test_survey_reward_then_signup_keeps_response_and_credit_without_regrant(self):
        fixture = fixtures.AnonymousServiceTest()
        fixture.setUp()
        fixture.service.execute(AnonymousSessionCommand("anon", Acquisition(campaign="exp001_run01")))
        account = fixture.credits.accounts["anon"]
        account.deduct()
        credit_repo = CreditRepository(account)
        responses = Responses()
        users = Mock()
        users.find_by_id = AsyncMock(side_effect=fixture.users.find_by_id)
        service = SubmitExperimentSurveyService(
            UserAcquisitionAdapter(GetUserAcquisitionCampaignService(users)),
            Completion(), CreditRewardAdapter(GrantExperimentRewardService(credit_repo)),
            responses, Transaction(),
        )
        await service.execute(valid_command(user_id="anon"))
        self.assertEqual(account.balance, 20)
        response = responses.added
        self.assertEqual(response.user_id, "anon")
        responses.existing = response
        result = fixture.social_service().execute(fixture.command())
        self.assertEqual(result.user_id, "anon")
        await service.execute(valid_command(user_id=result.user_id))
        self.assertEqual(account.balance, 20)
        self.assertEqual(fixture.credits.saves, 1)
        self.assertIs(responses.existing, response)

    async def test_zero_credit_does_not_gate_owned_result_but_other_account_is_rejected(self):
        fixture = fixtures.AnonymousServiceTest()
        fixture.setUp()
        fixture.service.execute(AnonymousSessionCommand("anon"))
        account = fixture.credits.accounts["anon"]
        account.deduct()
        account.deduct()
        self.assertEqual(account.balance, 0)
        asset = Asset("result", "anon", AssetType.ANIMATED, AssetCategory.COMPOSITION_RESULT, StorageUrl("https://example.test/result.gif"))
        assets = Mock()
        assets.find_by_id.return_value = asset
        users = Mock()
        users.is_active_user.return_value = True
        storage = Mock()
        storage.execute.return_value.bytes = b"GIF89a"
        download = DownloadAssetService(users, assets, storage)
        share = CreateShareLinkService(users, assets)
        self.assertEqual(download.execute(DownloadAssetCommand("anon", "result")).data, b"GIF89a")
        self.assertTrue(share.execute(CreateShareLinkCommand("anon", "result")).share_token)
        for caller in ("other-anonymous", "existing-member"):
            with self.assertRaises(AuthorizationException):
                download.execute(DownloadAssetCommand(caller, "result"))
            with self.assertRaises(AuthorizationException):
                share.execute(CreateShareLinkCommand(caller, "result"))
