from experiment.application.ports.inbound.get_experiment_survey_status import (
    GetExperimentSurveyStatusQuery,
    GetExperimentSurveyStatusResult,
)
from experiment.application.ports.outbound.domain_bridges.composition_completion_port import (
    CompositionCompletionPort,
)
from experiment.application.ports.outbound.domain_bridges.user_acquisition_port import (
    UserAcquisitionPort,
)
from experiment.application.ports.outbound.persistence.experiment_survey_response_repository import (
    ExperimentSurveyResponseRepository,
)
from experiment.application.services.experiment_policy import (
    ACQUISITION_CAMPAIGN,
    EXPERIMENT_CODE,
)


class GetExperimentSurveyStatusService:
    def __init__(
        self,
        user_acquisition: UserAcquisitionPort,
        composition_completion: CompositionCompletionPort,
        response_repo: ExperimentSurveyResponseRepository,
    ):
        self._user_acquisition = user_acquisition
        self._composition_completion = composition_completion
        self._response_repo = response_repo

    async def execute(
        self,
        query: GetExperimentSurveyStatusQuery,
    ) -> GetExperimentSurveyStatusResult:
        campaign = await self._user_acquisition.get_campaign(query.user_id)
        completed = (
            await self._composition_completion.has_completed(query.user_id)
            if campaign == ACQUISITION_CAMPAIGN
            else False
        )
        response = await self._response_repo.find_by_experiment_and_user(
            EXPERIMENT_CODE,
            query.user_id,
        )
        return GetExperimentSurveyStatusResult(
            eligible=campaign == ACQUISITION_CAMPAIGN and completed,
            submitted=response is not None,
        )
