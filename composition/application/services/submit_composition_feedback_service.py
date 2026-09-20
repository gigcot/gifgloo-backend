from composition.application.ports.inbound.submit_composition_feedback import (
    SubmitCompositionFeedbackCommand,
    SubmitCompositionFeedbackPort,
)
from composition.application.ports.outbound.persistence.async_composition_status_reader import (
    AsyncCompositionStatusReader,
)
from composition.application.ports.outbound.persistence.composition_feedback_repository import (
    CompositionFeedbackRepository,
)
from composition.application.ports.outbound.persistence.async_transaction import AsyncTransaction
from composition.domain.entities.composition_feedback import CompositionFeedback
from composition.domain.value_objects.composition_status import CompositionStatus
from shared.exceptions import AuthorizationException, InvalidStateException, NotFoundException


class SubmitCompositionFeedbackService(SubmitCompositionFeedbackPort):
    def __init__(
        self,
        status_reader: AsyncCompositionStatusReader,
        feedback_repo: CompositionFeedbackRepository,
        transaction: AsyncTransaction,
    ):
        self._status_reader = status_reader
        self._feedback_repo = feedback_repo
        self._transaction = transaction

    async def execute(self, command: SubmitCompositionFeedbackCommand) -> None:
        job = await self._status_reader.find_by_id(command.composition_job_id)
        if job is None:
            raise NotFoundException("합성 작업을 찾을 수 없습니다")
        if job.user_id != command.user_id:
            raise AuthorizationException("접근 권한이 없습니다")
        if job.status != CompositionStatus.COMPLETED:
            raise InvalidStateException("완료된 합성 작업만 평가할 수 있습니다")

        await self._feedback_repo.save(
            CompositionFeedback(
                composition_job_id=command.composition_job_id,
                satisfied=command.satisfied,
            )
        )
        await self._transaction.commit()
