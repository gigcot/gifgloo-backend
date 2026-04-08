from fastapi import Depends
from sqlalchemy.orm import Session

from config.database import get_db

# --- User domain ---
from user.adapter.outbound.persistence.sqlalchemy_user_repository import SqlAlchemyUserRepository
from user.application.services.verify_user_service import VerifyUserService

# --- Credit domain ---
from credit_account.adapter.outbound.sql_alchemy_credit_account_repository import SqlAlchemyCreditAccountRepository
from credit_account.adapter.outbound.user_verification import UserVerificationAdapter as CreditUserVerificationAdapter
from credit_account.application.services.check_balance_sufficient_service import CheckBalanceSufficientService
from credit_account.application.services.deduct_credit_service import DeductCreditService
from credit_account.application.services.refund_credit_service import RefundCreditService

# --- Asset domain ---
from asset.adapter.outbound.sql_alchemy_asset_repository import SqlAlchemyAssetRepository
from asset.adapter.outbound.r2_storage_adapter import R2UploadAdapter
from asset.adapter.outbound.user_verification import UserVerificationAdapter as AssetUserVerificationAdapter
from asset.application.services.save_asset_service import SaveAssetService

# --- Composition adapters ---
from composition.adapter.outbound.domain_bridges.user_verification_adapter import UserVerificationAdapter
from composition.adapter.outbound.domain_bridges.credit_adapter import CreditAdapter
from composition.adapter.outbound.domain_bridges.asset_save_adapter import AssetSaveAdapter
from composition.adapter.outbound.persistence.sqlalchemy_composition_repository import SqlAlchemyCompositionRepository
from composition.adapter.outbound.aws.lambda_feasibility_check_adapter import LambdaFeasibilityCheckAdapter
from composition.adapter.outbound.aws.r2_storage_adapter import R2StorageAdapter
from composition.adapter.outbound.aws.lambda_pipeline_trigger_adapter import LambdaPipelineTriggerAdapter

# --- Services ---
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
        feasibility=LambdaFeasibilityCheckAdapter(),
        storage=R2StorageAdapter(),
        asset_save=_make_asset_save_adapter(db),
        pipeline_trigger=LambdaPipelineTriggerAdapter(),
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
        storage=R2StorageAdapter(),
        credit=_make_credit_adapter(db),
    )
