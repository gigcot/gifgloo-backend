from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.sqlalchemy_async_composition_repository import (
    SqlAlchemyAsyncCompositionRepository,
)
from composition.application.services.has_completed_composition_service import (
    HasCompletedCompositionService,
)
from config.database import get_async_db
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import (
    SqlAlchemyAsyncCreditAccountRepository,
)
from credit_account.application.services.grant_experiment_reward_service import (
    GrantExperimentRewardService,
)
from experiment.adapter.outbound.domain_bridges.composition_completion_adapter import (
    CompositionCompletionAdapter,
)
from experiment.adapter.outbound.domain_bridges.credit_reward_adapter import (
    CreditRewardAdapter,
)
from experiment.adapter.outbound.domain_bridges.user_acquisition_adapter import (
    UserAcquisitionAdapter,
)
from experiment.adapter.outbound.persistence.sqlalchemy_async_transaction import (
    SqlAlchemyAsyncTransaction,
)
from experiment.adapter.outbound.persistence.sqlalchemy_experiment_survey_response_repository import (
    SqlAlchemyExperimentSurveyResponseRepository,
)
from experiment.application.services.get_experiment_survey_status_service import (
    GetExperimentSurveyStatusService,
)
from experiment.application.services.submit_experiment_survey_service import (
    SubmitExperimentSurveyService,
)
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import (
    SqlAlchemyAsyncUserRepository,
)
from user.application.services.get_user_acquisition_campaign_service import (
    GetUserAcquisitionCampaignService,
)


def _make_user_acquisition_adapter(db: AsyncSession) -> UserAcquisitionAdapter:
    return UserAcquisitionAdapter(
        GetUserAcquisitionCampaignService(SqlAlchemyAsyncUserRepository(db))
    )


def _make_composition_completion_adapter(
    db: AsyncSession,
) -> CompositionCompletionAdapter:
    return CompositionCompletionAdapter(
        HasCompletedCompositionService(SqlAlchemyAsyncCompositionRepository(db))
    )


def get_experiment_survey_status_service(
    db: AsyncSession = Depends(get_async_db),
) -> GetExperimentSurveyStatusService:
    return GetExperimentSurveyStatusService(
        user_acquisition=_make_user_acquisition_adapter(db),
        composition_completion=_make_composition_completion_adapter(db),
        response_repo=SqlAlchemyExperimentSurveyResponseRepository(db),
    )


def get_submit_experiment_survey_service(
    db: AsyncSession = Depends(get_async_db),
) -> SubmitExperimentSurveyService:
    return SubmitExperimentSurveyService(
        user_acquisition=_make_user_acquisition_adapter(db),
        composition_completion=_make_composition_completion_adapter(db),
        credit_reward=CreditRewardAdapter(
            GrantExperimentRewardService(
                SqlAlchemyAsyncCreditAccountRepository(db)
            )
        ),
        response_repo=SqlAlchemyExperimentSurveyResponseRepository(db),
        transaction=SqlAlchemyAsyncTransaction(db),
    )
