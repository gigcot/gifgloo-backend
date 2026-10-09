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

    async def create_once(self, feedback: CompositionFeedback) -> bool:
        statement = insert(CompositionFeedbackModel).values(
            composition_job_id=feedback.composition_job_id,
            satisfied=feedback.satisfied,
            created_at=feedback.created_at,
            updated_at=feedback.updated_at,
        )
        result = await self._session.execute(
            statement.on_conflict_do_nothing(
                index_elements=[CompositionFeedbackModel.composition_job_id],
            ).returning(CompositionFeedbackModel.composition_job_id)
        )
        return result.scalar_one_or_none() is not None

    async def find_by_job_id(self, composition_job_id: str) -> CompositionFeedback | None:
        model = await self._session.get(CompositionFeedbackModel, composition_job_id)
        if model is None:
            return None
        return CompositionFeedback(
            composition_job_id=model.composition_job_id,
            satisfied=model.satisfied,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
