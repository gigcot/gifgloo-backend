from datetime import datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from composition.adapter.outbound.persistence.models import CompositionGateModel
from composition.application.ports.outbound.persistence.composition_gate_repository import CompositionGateRepository
from composition.domain.aggregates.composition_gate import CompositionGate


class SqlAlchemyCompositionGateRepository(CompositionGateRepository):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def has_active_lease(self, now: datetime) -> bool:
        return (
            await self._session.execute(
                select(CompositionGateModel.id)
                .where(CompositionGateModel.id == 1)
                .where(CompositionGateModel.active_job_id.is_not(None))
                .where(CompositionGateModel.lease_until > now)
            )
        ).scalar_one_or_none() is not None

    async def find_expired_job_id(self, now: datetime) -> str | None:
        return (
            await self._session.execute(
                select(CompositionGateModel.active_job_id)
                .where(CompositionGateModel.id == 1)
                .where(CompositionGateModel.lease_until <= now)
            )
        ).scalar_one_or_none()

    async def find_for_update(self) -> CompositionGate:
        model = (
            await self._session.execute(
                select(CompositionGateModel)
                .where(CompositionGateModel.id == 1)
                .with_for_update()
            )
        ).scalar_one()
        return CompositionGate(
            active_job_id=model.active_job_id,
            active_run_id=model.active_run_id,
            lease_until=model.lease_until,
            last_edit_sent_at=model.last_edit_sent_at,
        )

    async def update(self, gate: CompositionGate) -> None:
        await self._session.execute(
            update(CompositionGateModel)
            .where(CompositionGateModel.id == 1)
            .values(
                active_job_id=gate.active_job_id,
                active_run_id=gate.active_run_id,
                lease_until=gate.lease_until,
                last_edit_sent_at=gate.last_edit_sent_at,
            )
        )
