from abc import ABC, abstractmethod

from experiment.domain.aggregates.experiment_survey_response import (
    ExperimentSurveyResponse,
)


class ExperimentSurveyResponseRepository(ABC):
    @abstractmethod
    async def find_by_experiment_and_user(
        self,
        experiment_code: str,
        user_id: str,
    ) -> ExperimentSurveyResponse | None:
        pass

    @abstractmethod
    async def add_if_absent(self, response: ExperimentSurveyResponse) -> bool:
        pass
