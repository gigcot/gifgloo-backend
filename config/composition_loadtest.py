import os
from enum import Enum

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from config.database import AsyncSessionLocal, get_async_db, get_db

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
from composition.adapter.outbound.domain_bridges.async_asset_save_adapter import AsyncAssetSaveAdapter
from composition.adapter.outbound.domain_bridges.async_credit_adapter import AsyncCreditAdapter
from composition.adapter.outbound.domain_bridges.async_user_verification_adapter import AsyncUserVerificationAdapter
from composition.adapter.outbound.persistence.sqlalchemy_async_composition_status_reader import (
    SqlAlchemyAsyncCompositionStatusReader,
)
from composition.adapter.outbound.persistence.sqlalchemy_composition_repository import SqlAlchemyCompositionRepository
from composition.adapter.outbound.persistence.sqlalchemy_async_composition_writer import SqlAlchemyAsyncCompositionWriter
from composition.adapter.outbound.persistence.sqlalchemy_async_transaction import SqlAlchemyAsyncTransaction
from composition.adapter.outbound.loadtest.fake_feasibility_check_adapter import FakeFeasibilityCheckAdapter
from composition.adapter.outbound.loadtest.fake_pipeline_trigger_adapter import FakePipelineTriggerAdapter
from composition.adapter.outbound.loadtest.fake_pipeline_worker_trigger_adapter import (
    FakePipelineWorkerTriggerAdapter,
)
from composition.adapter.outbound.loadtest.fake_storage_adapter import FakeStorageAdapter

from composition.application.services.request_composition_service import RequestCompositionService
from composition.application.services.get_composition_status_service import GetCompositionStatusService
from composition.application.services.get_composition_list_service import GetCompositionListService
from composition.application.services.pipeline_callback_service import PipelineCallbackService
from composition.application.ports.outbound.aws.pipeline_trigger_port import PipelineTriggerPort
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import SqlAlchemyAsyncUserRepository
from user.application.services.async_verify_user_service import AsyncVerifyUserService
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import SqlAlchemyAsyncCreditAccountRepository
from credit_account.application.services.async_credit_service import AsyncCreditService
from asset.adapter.outbound.sqlalchemy_async_asset_repository import SqlAlchemyAsyncAssetRepository
from asset.application.services.async_save_asset_from_url_service import AsyncSaveAssetFromUrlService


class PipelineMode(Enum):
    IN_PROCESS = "in_process"
    EXTERNAL = "external"


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


def _make_async_verify_user_service(db: AsyncSession) -> AsyncVerifyUserService:
    return AsyncVerifyUserService(SqlAlchemyAsyncUserRepository(db))


def _make_async_credit_adapter(db: AsyncSession) -> AsyncCreditAdapter:
    return AsyncCreditAdapter(
        AsyncCreditService(
            user_verification=_make_async_verify_user_service(db),
            credit_account_repo=SqlAlchemyAsyncCreditAccountRepository(db),
        )
    )


def _make_async_asset_save_adapter(db: AsyncSession) -> AsyncAssetSaveAdapter:
    return AsyncAssetSaveAdapter(
        AsyncSaveAssetFromUrlService(
            user_verification=_make_async_verify_user_service(db),
            asset_repo=SqlAlchemyAsyncAssetRepository(db),
        )
    )


def _make_pipeline_trigger() -> PipelineTriggerPort:
    mode = (
        PipelineMode(os.environ["LOADTEST_PIPELINE_MODE"])
        if "LOADTEST_PIPELINE_MODE" in os.environ
        else PipelineMode.IN_PROCESS
    )
    if mode is PipelineMode.IN_PROCESS:
        return FakePipelineTriggerAdapter()
    return FakePipelineWorkerTriggerAdapter()


def get_request_composition_service(db: AsyncSession = Depends(get_async_db)) -> RequestCompositionService:
    return RequestCompositionService(
        user_verification=AsyncUserVerificationAdapter(_make_async_verify_user_service(db)),
        credit=_make_async_credit_adapter(db),
        feasibility=FakeFeasibilityCheckAdapter(),
        storage=FakeStorageAdapter(),
        asset_save=_make_async_asset_save_adapter(db),
        pipeline_trigger=_make_pipeline_trigger(),
        composition_repo=SqlAlchemyAsyncCompositionWriter(db),
        transaction=SqlAlchemyAsyncTransaction(db),
    )


def get_composition_list_service(db: Session = Depends(get_db, scope="function")) -> GetCompositionListService:
    return GetCompositionListService(
        composition_repo=SqlAlchemyCompositionRepository(db),
    )


def get_composition_status_service() -> GetCompositionStatusService:
    return GetCompositionStatusService(
        status_reader=SqlAlchemyAsyncCompositionStatusReader(AsyncSessionLocal),
    )


def get_pipeline_callback_service(db: Session = Depends(get_db)) -> PipelineCallbackService:
    return PipelineCallbackService(
        composition_repo=SqlAlchemyCompositionRepository(db),
        asset_save=_make_asset_save_adapter(db),
        storage=FakeStorageAdapter(),
        credit=_make_credit_adapter(db),
    )
