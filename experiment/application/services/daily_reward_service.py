from experiment.application.ports.outbound.domain_bridges.daily_reward_port import DailyRewardPort, DailyRewardResult
from experiment.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from experiment.application.ports.outbound.persistence.experiment_survey_response_repository import ExperimentSurveyResponseRepository
from experiment.application.services.experiment_policy import EXPERIMENT_CODE
from shared.exceptions import AuthorizationException


class DailyRewardService:
    def __init__(self, responses: ExperimentSurveyResponseRepository, rewards: DailyRewardPort, transaction: AsyncTransaction):
        self._responses = responses
        self._rewards = rewards
        self._transaction = transaction

    async def _require_survey(self, user_id: str) -> None:
        response = await self._responses.find_by_experiment_and_user(EXPERIMENT_CODE, user_id)
        if response is None:
            raise AuthorizationException("설문에 한 번 참여하면 매일 3회를 받을 수 있습니다")

    async def get_status(self, user_id: str) -> DailyRewardResult:
        await self._require_survey(user_id)
        return await self._rewards.get_status(user_id)

    async def claim(self, user_id: str) -> DailyRewardResult:
        try:
            await self._require_survey(user_id)
            result = await self._rewards.claim(user_id)
            await self._transaction.commit()
            return result
        except Exception:
            await self._transaction.rollback()
            raise
