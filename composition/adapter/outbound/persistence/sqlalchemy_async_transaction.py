from sqlalchemy.ext.asyncio import AsyncSession

from composition.application.ports.outbound.persistence.async_transaction import AsyncTransaction


class SqlAlchemyAsyncTransaction(AsyncTransaction):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def commit(self) -> None:
        await self._session.commit()

    async def rollback(self) -> None:
        await self._session.rollback()
