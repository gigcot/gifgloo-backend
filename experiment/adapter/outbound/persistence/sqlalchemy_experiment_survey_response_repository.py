from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from experiment.adapter.outbound.persistence.models import (
    ExperimentSurveyResponseModel,
)
from experiment.application.ports.outbound.persistence.experiment_survey_response_repository import (
    ExperimentSurveyResponseRepository,
)
from experiment.domain.aggregates.experiment_survey_response import (
    ExperimentSurveyResponse,
)


def _to_domain(model: ExperimentSurveyResponseModel) -> ExperimentSurveyResponse:
    return ExperimentSurveyResponse(
        id=model.id,
        experiment_code=model.experiment_code,
        user_id=model.user_id,
        answers=model.answers,
        submitted_at=model.submitted_at,
    )


class SqlAlchemyExperimentSurveyResponseRepository(
    ExperimentSurveyResponseRepository
):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def find_by_experiment_and_user(
        self,
        experiment_code: str,
        user_id: str,
    ) -> ExperimentSurveyResponse | None:
        statement = select(ExperimentSurveyResponseModel).where(
            ExperimentSurveyResponseModel.experiment_code == experiment_code,
            ExperimentSurveyResponseModel.user_id == user_id,
        )
        model = (await self._session.execute(statement)).scalar_one_or_none()
        return _to_domain(model) if model else None

    async def add_if_absent(self, response: ExperimentSurveyResponse) -> bool:
        statement = (
            insert(ExperimentSurveyResponseModel)
            .values(
                id=response.id,
                experiment_code=response.experiment_code,
                user_id=response.user_id,
                answers=response.answers,
                submitted_at=response.submitted_at,
            )
            .on_conflict_do_nothing(
                constraint="uq_experiment_survey_responses_experiment_user"
            )
            .returning(ExperimentSurveyResponseModel.id)
        )
        inserted_id = (await self._session.execute(statement)).scalar_one_or_none()
        return inserted_id is not None
