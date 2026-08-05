from datetime import datetime, timezone
import uuid

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from payment.adapter.outbound.persistence.models import PaymentInboxModel
from payment.application.ports.outbound.inbox.payment_inbox_port import (
    AcquirePaymentInboxCommand,
    AcquirePaymentInboxResult,
    PaymentInboxPort,
)
from payment.domain.value_objects.payment_provider import PaymentProvider
from shared.exceptions import InvalidStateException, NotFoundException


_RECEIVED = "RECEIVED"
_PROCESSED = "PROCESSED"


class SqlAlchemyPaymentInbox(PaymentInboxPort):
    def __init__(self, session: AsyncSession):
        self._session = session

    async def acquire(
        self,
        command: AcquirePaymentInboxCommand,
    ) -> AcquirePaymentInboxResult:
        now = datetime.now(timezone.utc)
        statement = (
            insert(PaymentInboxModel)
            .values(
                id=str(uuid.uuid4()),
                provider=command.provider.value,
                external_event_id=command.external_event_id,
                event_type=command.event_type,
                order_id=command.order_id,
                payload=command.payload,
                status=_RECEIVED,
                attempts=1,
                received_at=now,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    PaymentInboxModel.provider,
                    PaymentInboxModel.external_event_id,
                ]
            )
            .returning(PaymentInboxModel.id)
        )
        inserted_id = (await self._session.execute(statement)).scalar_one_or_none()
        if inserted_id is not None:
            return AcquirePaymentInboxResult(
                already_processed=False,
                payment_id=None,
            )

        existing_statement = (
            select(PaymentInboxModel)
            .where(
                PaymentInboxModel.provider == command.provider.value,
                PaymentInboxModel.external_event_id == command.external_event_id,
            )
            .with_for_update()
        )
        existing = (
            await self._session.execute(existing_statement)
        ).scalar_one_or_none()
        if existing is None:
            raise NotFoundException("결제 수신 기록을 찾을 수 없습니다")
        if existing.order_id != command.order_id:
            raise InvalidStateException("동일한 외부 이벤트에 다른 주문이 연결되었습니다")
        if existing.event_type != command.event_type:
            raise InvalidStateException("동일한 외부 이벤트의 종류가 일치하지 않습니다")
        if existing.status == _PROCESSED:
            return AcquirePaymentInboxResult(
                already_processed=True,
                payment_id=existing.payment_id,
            )

        existing.payload = command.payload
        existing.attempts += 1
        await self._session.flush()
        return AcquirePaymentInboxResult(
            already_processed=False,
            payment_id=None,
        )

    async def mark_processed(
        self,
        provider: PaymentProvider,
        external_event_id: str,
        payment_id: str,
    ) -> None:
        statement = (
            update(PaymentInboxModel)
            .where(
                PaymentInboxModel.provider == provider.value,
                PaymentInboxModel.external_event_id == external_event_id,
            )
            .values(
                payment_id=payment_id,
                status=_PROCESSED,
                processed_at=datetime.now(timezone.utc),
            )
        )
        result = await self._session.execute(statement)
        if result.rowcount != 1:
            raise NotFoundException("완료 처리할 결제 수신 기록을 찾을 수 없습니다")
        await self._session.flush()
