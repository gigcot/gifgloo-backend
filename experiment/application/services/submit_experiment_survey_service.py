from experiment.application.ports.inbound.submit_experiment_survey import (
    SubmitExperimentSurveyCommand,
    SubmitExperimentSurveyResult,
)
from experiment.application.ports.outbound.domain_bridges.composition_completion_port import (
    CompositionCompletionPort,
)
from experiment.application.ports.outbound.domain_bridges.credit_reward_port import (
    CreditRewardPort,
    GrantExperimentRewardCommand,
)
from experiment.application.ports.outbound.domain_bridges.user_acquisition_port import (
    UserAcquisitionPort,
)
from experiment.application.ports.outbound.persistence.async_transaction import (
    AsyncTransaction,
)
from experiment.application.ports.outbound.persistence.experiment_survey_response_repository import (
    ExperimentSurveyResponseRepository,
)
from experiment.application.services.experiment_policy import (
    ACQUISITION_CAMPAIGN,
    EXPERIMENT_CODE,
)
from experiment.domain.aggregates.experiment_survey_response import (
    ExperimentSurveyResponse,
)
from experiment.domain.value_objects.experiment_survey_answers import (
    ExperimentSurveyAnswers,
)
from shared.exceptions import AuthorizationException


class SubmitExperimentSurveyService:
    def __init__(
        self,
        user_acquisition: UserAcquisitionPort,
        composition_completion: CompositionCompletionPort,
        credit_reward: CreditRewardPort,
        response_repo: ExperimentSurveyResponseRepository,
        transaction: AsyncTransaction,
    ):
        self._user_acquisition = user_acquisition
        self._composition_completion = composition_completion
        self._credit_reward = credit_reward
        self._response_repo = response_repo
        self._transaction = transaction

    async def execute(
        self,
        command: SubmitExperimentSurveyCommand,
    ) -> SubmitExperimentSurveyResult:
        answers = ExperimentSurveyAnswers(
            intended_context=command.intended_context,
            actual_actions=command.actual_actions,
            intended_context_other=command.intended_context_other,
            actual_action_other=command.actual_action_other,
            non_external_use_reasons=command.non_external_use_reasons,
            non_external_use_reason_other=command.non_external_use_reason_other,
            next_context=command.next_context,
        )
        try:
            existing = await self._response_repo.find_by_experiment_and_user(
                EXPERIMENT_CODE,
                command.user_id,
            )
            if existing is not None:
                await self._transaction.commit()
                return SubmitExperimentSurveyResult(submitted=True)

            campaign = await self._user_acquisition.get_campaign(command.user_id)
            if campaign != ACQUISITION_CAMPAIGN:
                raise AuthorizationException("EXP-001 설문 대상자가 아닙니다")
            if not await self._composition_completion.has_completed(command.user_id):
                raise AuthorizationException("EXP-001 설문 대상자가 아닙니다")

            response = ExperimentSurveyResponse(
                experiment_code=EXPERIMENT_CODE,
                user_id=command.user_id,
                answers=answers.to_dict(),
            )
            inserted = await self._response_repo.add_if_absent(response)
            if inserted:
                await self._credit_reward.grant(
                    GrantExperimentRewardCommand(
                        user_id=command.user_id,
                        response_id=response.id,
                        granted_at=response.submitted_at,
                    )
                )
            await self._transaction.commit()
            return SubmitExperimentSurveyResult(submitted=True)
        except Exception:
            await self._transaction.rollback()
            raise
