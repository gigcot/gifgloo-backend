from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db

from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.application.services.verify_user_service import VerifyUserService

from credit_account.adapter.outbound.sql_alchemy_credit_account_repository import SqlAlchemyCreditAccountRepository
from credit_account.adapter.outbound.user_verification import UserVerificationAdapter as CreditUserVerificationAdapter
from credit_account.application.services.check_balance_sufficient_service import CheckBalanceSufficientService
from credit_account.application.services.deduct_credit_service import DeductCreditService
from credit_account.application.services.refund_credit_service import RefundCreditService

from asset.adapter.outbound.sql_alchemy_asset_repository import SqlAlchemyAssetRepository
from asset.adapter.outbound.r2_storage_adapter import R2UploadAdapter
from asset.adapter.outbound.user_verification import UserVerificationAdapter as AssetUserVerificationAdapter
from asset.application.services.save_asset_service import SaveAssetService

from composition.adapter.outbound.domain_bridges.user_verification_adapter import UserVerificationAdapter
from composition.adapter.outbound.domain_bridges.credit_adapter import CreditAdapter
from composition.adapter.outbound.domain_bridges.asset_save_adapter import AssetSaveAdapter
from composition.adapter.outbound.persistence.sqlalchemy_composition_repository import SqlAlchemyCompositionRepository
from composition.adapter.outbound.loadtest.fake_feasibility_check_adapter import FakeFeasibilityCheckAdapter
from composition.adapter.outbound.loadtest.fake_pipeline_trigger_adapter import FakePipelineTriggerAdapter
from composition.adapter.outbound.loadtest.fake_storage_adapter import FakeStorageAdapter

from composition.application.services.request_composition_service import RequestCompositionService
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.services.get_composition_list_service import GetCompositionListService
from composition.application.services.pipeline_callback_service import PipelineCallbackService


def _make_credit_adapter(db: Session) -> CreditAdapter:
    user_repo = SqlAlchemyUserRepository(db)
    verify_user_service = VerifyUserService(user_repo)
    credit_repo = SqlAlchemyCreditAccountRepository(db)
    return CreditAdapter(
        check_balance_service=CheckBalanceSufficientService(credit_repo),
        deduct_service=DeductCreditService(CreditUserVerificationAdapter(verify_user_service), credit_repo),
        refund_service=RefundCreditService(credit_repo),
    )


def _make_asset_save_adapter(db: Session) -> AssetSaveAdapter:
    user_repo = SqlAlchemyUserRepository(db)
    verify_user_service = VerifyUserService(user_repo)
    asset_repo = SqlAlchemyAssetRepository(db)
    return AssetSaveAdapter(
        SaveAssetService(AssetUserVerificationAdapter(verify_user_service), asset_repo, R2UploadAdapter())
    )


def get_request_composition_service(db: Session = Depends(get_db)) -> RequestCompositionService:
    return RequestCompositionService(
        user_verification=UserVerificationAdapter(VerifyUserService(SqlAlchemyUserRepository(db))),
        credit=_make_credit_adapter(db),
        feasibility=FakeFeasibilityCheckAdapter(),
        storage=FakeStorageAdapter(),
        asset_save=_make_asset_save_adapter(db),
        pipeline_trigger=FakePipelineTriggerAdapter(),
        composition_repo=SqlAlchemyCompositionRepository(db),
    )


def get_composition_status_service(db: Session = Depends(get_db)) -> GetCompositionStatusService:
    return GetCompositionStatusService(
        composition_repo=SqlAlchemyCompositionRepository(db),
    )


def get_composition_list_service(db: Session = Depends(get_db)) -> GetCompositionListService:
    return GetCompositionListService(
        composition_repo=SqlAlchemyCompositionRepository(db),
    )


def get_pipeline_callback_service(db: Session = Depends(get_db)) -> PipelineCallbackService:
    return PipelineCallbackService(
        composition_repo=SqlAlchemyCompositionRepository(db),
        asset_save=_make_asset_save_adapter(db),
        storage=FakeStorageAdapter(),
        credit=_make_credit_adapter(db),
    )
