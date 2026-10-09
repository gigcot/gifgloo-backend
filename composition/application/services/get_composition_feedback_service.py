from composition.application.ports.inbound.get_composition_feedback import (
    GetCompositionFeedbackCommand,
    GetCompositionFeedbackPort,
    GetCompositionFeedbackResult,
)
from composition.application.ports.outbound.persistence.async_composition_status_reader import (
    AsyncCompositionStatusReader,
)
from composition.application.ports.outbound.persistence.composition_feedback_repository import (
    CompositionFeedbackRepository,
)
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import AuthorizationException, InvalidStateException, NotFoundException


class GetCompositionFeedbackService(GetCompositionFeedbackPort):
    def __init__(
        self,
        status_reader: AsyncCompositionStatusReader,
        feedback_repo: CompositionFeedbackRepository,
    ):
        self._status_reader = status_reader
        self._feedback_repo = feedback_repo

    async def execute(self, command: GetCompositionFeedbackCommand) -> GetCompositionFeedbackResult:
        job = await self._status_reader.find_by_id(command.composition_job_id)
        if job is None:
            raise NotFoundException("합성 작업을 찾을 수 없습니다")
        if job.user_id != command.user_id:
            raise AuthorizationException("접근 권한이 없습니다")
        if job.status != CompositionStatus.COMPLETED:
            raise InvalidStateException("완료된 합성 작업만 평가할 수 있습니다")

        feedback = await self._feedback_repo.find_by_job_id(command.composition_job_id)
        return GetCompositionFeedbackResult(satisfied=feedback.satisfied if feedback else None)
