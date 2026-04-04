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
from composition.adapter.outbound.aws.lambda_gif_processing_adapter import LambdaGifProcessingAdapter
from composition.adapter.outbound.aws.r2_storage_adapter import R2StorageAdapter
from composition.adapter.outbound.ai.lambda_composition_analysis_adapter import LambdaCompositionAnalysisAdapter
from composition.adapter.outbound.ai.lambda_inpainting_adapter import LambdaInpaintingAdapter

# --- Services ---
from composition.application.services.request_composition_service import RequestCompositionService
from composition.application.services.get_composition_status_service import GetCompositionStatusService


def get_request_composition_service(db: Session = Depends(get_db)) -> RequestCompositionService:
    # 공통: User 검증 서비스
    user_repo = SqlAlchemyUserRepository(db)
    verify_user_service = VerifyUserService(user_repo)

    # Credit 서비스들
    credit_repo = SqlAlchemyCreditAccountRepository(db)
    credit_user_verification = CreditUserVerificationAdapter(verify_user_service)
    check_balance_service = CheckBalanceSufficientService(credit_repo)
    deduct_service = DeductCreditService(credit_user_verification, credit_repo)
    refund_service = RefundCreditService(credit_repo)

    # Asset 저장 서비스
    asset_repo = SqlAlchemyAssetRepository(db)
    asset_user_verification = AssetUserVerificationAdapter(verify_user_service)
    asset_storage = R2UploadAdapter()
    save_asset_service = SaveAssetService(asset_user_verification, asset_repo, asset_storage)

    return RequestCompositionService(
        user_verification=UserVerificationAdapter(verify_user_service),
        credit=CreditAdapter(check_balance_service, deduct_service, refund_service),
        feasibility=LambdaFeasibilityCheckAdapter(),
        gif_processor=LambdaGifProcessingAdapter(),
        analysis=LambdaCompositionAnalysisAdapter(),
        inpainting=LambdaInpaintingAdapter(),
        storage=R2StorageAdapter(),
        asset_save=AssetSaveAdapter(save_asset_service),
        composition_repo=SqlAlchemyCompositionRepository(db),
    )


def get_composition_status_service(db: Session = Depends(get_db)) -> GetCompositionStatusService:
    return GetCompositionStatusService(
        composition_repo=SqlAlchemyCompositionRepository(db),
    )
