from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.models import CompositionFeedbackModel
from composition.application.ports.outbound.persistence.composition_feedback_repository import (
    CompositionFeedbackRepository,
)
from composition.domain.entities.composition_feedback import CompositionFeedback


class SqlAlchemyCompositionFeedbackRepository(CompositionFeedbackRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def save(self, feedback: CompositionFeedback) -> None:
        statement = insert(CompositionFeedbackModel).values(
            composition_job_id=feedback.composition_job_id,
            satisfied=feedback.satisfied,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )
        await self._session.execute(
            statement.on_conflict_do_update(
                index_elements=[CompositionFeedbackModel.composition_job_id],
                set_={
                    "satisfied": feedback.satisfied,
                    "updated_at": feedback.updated_at,
                },
            )
        )
