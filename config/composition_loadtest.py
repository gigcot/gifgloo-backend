import os
from enum import Enum

import httpx
from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import AsyncSessionLocal, get_async_db

from composition.adapter.outbound.domain_bridges.async_asset_create_adapter import AsyncAssetCreateAdapter
from composition.adapter.outbound.domain_bridges.async_credit_adapter import AsyncCreditAdapter
from composition.adapter.outbound.domain_bridges.async_user_verification_adapter import AsyncUserVerificationAdapter
from composition.adapter.outbound.persistence.sqlalchemy_async_composition_status_reader import (
    SqlAlchemyAsyncCompositionStatusReader,
)
from composition.adapter.outbound.persistence.sqlalchemy_async_composition_repository import (
    SqlAlchemyAsyncCompositionRepository,
)
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
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import SqlAlchemyAsyncUserRepository
from user.application.services.async_verify_user_service import AsyncVerifyUserService
from credit_account.adapter.outbound.async_user_verification import (
    AsyncUserVerificationAdapter as CreditUserVerificationAdapter,
)
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import SqlAlchemyAsyncCreditAccountRepository
from credit_account.application.services.async_credit_service import AsyncCreditService
from asset.adapter.outbound.sqlalchemy_async_asset_repository import SqlAlchemyAsyncAssetRepository
from asset.application.services.async_create_asset_from_url_service import AsyncCreateAssetFromUrlService


class PipelineMode(Enum):
    IN_PROCESS = "in_process"
    EXTERNAL = "external"


def _make_async_verify_user_service(db: AsyncSession) -> AsyncVerifyUserService:
    return AsyncVerifyUserService(SqlAlchemyAsyncUserRepository(db))


def _make_async_credit_adapter(db: AsyncSession) -> AsyncCreditAdapter:
    return AsyncCreditAdapter(
        AsyncCreditService(
            user_verification=CreditUserVerificationAdapter(_make_async_verify_user_service(db)),
            credit_account_repo=SqlAlchemyAsyncCreditAccountRepository(db),
        )
    )


def _make_async_asset_create_adapter(db: AsyncSession) -> AsyncAssetCreateAdapter:
    return AsyncAssetCreateAdapter(
        AsyncCreateAssetFromUrlService(SqlAlchemyAsyncAssetRepository(db))
    )


def create_pipeline_trigger(
    client: httpx.AsyncClient,
) -> FakePipelineTriggerAdapter | FakePipelineWorkerTriggerAdapter:
    mode = (
        PipelineMode(os.environ["LOADTEST_PIPELINE_MODE"])
        if "LOADTEST_PIPELINE_MODE" in os.environ
        else PipelineMode.IN_PROCESS
    )
    if mode is PipelineMode.IN_PROCESS:
        return FakePipelineTriggerAdapter(client)
    return FakePipelineWorkerTriggerAdapter(client)


def get_request_composition_service(
    request: Request,
    db: AsyncSession = Depends(get_async_db),
) -> RequestCompositionService:
    return RequestCompositionService(
        user_verification=AsyncUserVerificationAdapter(_make_async_verify_user_service(db)),
        credit=_make_async_credit_adapter(db),
        feasibility=FakeFeasibilityCheckAdapter(),
        storage=FakeStorageAdapter(),
        asset_save=_make_async_asset_create_adapter(db),
        pipeline_trigger=request.app.state.pipeline_trigger,
        composition_repo=SqlAlchemyAsyncCompositionRepository(db),
        transaction=SqlAlchemyAsyncTransaction(db),
    )


def get_composition_list_service(
    db: AsyncSession = Depends(get_async_db),
) -> GetCompositionListService:
    return GetCompositionListService(
        composition_repo=SqlAlchemyAsyncCompositionRepository(db),
    )


def get_composition_status_service() -> GetCompositionStatusService:
    return GetCompositionStatusService(
        status_reader=SqlAlchemyAsyncCompositionStatusReader(AsyncSessionLocal),
    )


def get_pipeline_callback_service(
    db: AsyncSession = Depends(get_async_db),
) -> PipelineCallbackService:
    return PipelineCallbackService(
        composition_repo=SqlAlchemyAsyncCompositionRepository(db),
        asset_save=_make_async_asset_create_adapter(db),
        storage=FakeStorageAdapter(),
        credit=_make_async_credit_adapter(db),
        user_verification=AsyncUserVerificationAdapter(_make_async_verify_user_service(db)),
        transaction=SqlAlchemyAsyncTransaction(db),
    )
