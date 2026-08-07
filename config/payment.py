import os

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from config.database import get_async_db
from credit_account.adapter.outbound.sqlalchemy_async_credit_account_repository import (
    SqlAlchemyAsyncCreditAccountRepository,
)
from credit_account.application.services.grant_payment_credit_service import (
    GrantPaymentCreditService,
)
from payment.adapter.outbound.domain_bridges.async_credit_grant_adapter import (
    AsyncCreditGrantAdapter,
)
from payment.adapter.outbound.domain_bridges.async_user_verification_adapter import (
    AsyncUserVerificationAdapter,
)
from payment.adapter.outbound.persistence.sqlalchemy_async_payment_repository import (
    SqlAlchemyAsyncPaymentRepository,
)
from payment.adapter.outbound.persistence.sqlalchemy_async_transaction import (
    SqlAlchemyAsyncTransaction,
)
from payment.adapter.outbound.persistence.sqlalchemy_payment_inbox import (
    SqlAlchemyPaymentInbox,
)
from payment.adapter.outbound.payment_gateway.toss_pay_http_adapter import (
    TossPayHttpAdapter,
)
from payment.application.services.create_payment_order_service import (
    CreatePaymentOrderService,
)
from payment.application.services.process_verified_payment_service import (
    ProcessVerifiedPaymentService,
)
from payment.application.services.handle_toss_pay_callback_service import (
    HandleTossPayCallbackService,
)
from config.payment_settings import required_payment_env
from user.adapter.outbound.persistence.sqlalchemy_async_user_repository import (
    SqlAlchemyAsyncUserRepository,
)
from user.application.services.async_verify_user_service import AsyncVerifyUserService


def _get_toss_pay_gateway() -> TossPayHttpAdapter:
    return TossPayHttpAdapter(
        api_key=required_payment_env("TOSS_PAY_API_KEY"),
        result_callback_url=required_payment_env("TOSS_PAY_RESULT_CALLBACK_URL"),
        return_url=required_payment_env("TOSS_PAY_RETURN_URL"),
        cancel_url=required_payment_env("TOSS_PAY_CANCEL_URL"),
        base_url=os.getenv("TOSS_PAY_BASE_URL", "https://pay.toss.im/api/v2"),
    )


def get_create_payment_order_service(
    db: AsyncSession = Depends(get_async_db),
) -> CreatePaymentOrderService:
    return CreatePaymentOrderService(
        user_verification=AsyncUserVerificationAdapter(
            AsyncVerifyUserService(SqlAlchemyAsyncUserRepository(db))
        ),
        payment_repo=SqlAlchemyAsyncPaymentRepository(db),
        transaction=SqlAlchemyAsyncTransaction(db),
        toss_pay_gateway=_get_toss_pay_gateway(),
    )


def get_process_verified_payment_service(
    db: AsyncSession = Depends(get_async_db),
) -> ProcessVerifiedPaymentService:
    return ProcessVerifiedPaymentService(
        payment_repo=SqlAlchemyAsyncPaymentRepository(db),
        inbox=SqlAlchemyPaymentInbox(db),
        credit=AsyncCreditGrantAdapter(
            GrantPaymentCreditService(
                SqlAlchemyAsyncCreditAccountRepository(db)
            )
        ),
        transaction=SqlAlchemyAsyncTransaction(db),
    )


def get_handle_toss_pay_callback_service(
    db: AsyncSession = Depends(get_async_db),
) -> HandleTossPayCallbackService:
    payment_repo = SqlAlchemyAsyncPaymentRepository(db)
    transaction = SqlAlchemyAsyncTransaction(db)
    return HandleTossPayCallbackService(
        toss_pay_gateway=_get_toss_pay_gateway(),
        process_payment=ProcessVerifiedPaymentService(
            payment_repo=payment_repo,
            inbox=SqlAlchemyPaymentInbox(db),
            credit=AsyncCreditGrantAdapter(
                GrantPaymentCreditService(
                    SqlAlchemyAsyncCreditAccountRepository(db)
                )
            ),
            transaction=transaction,
        ),
        payment_repo=payment_repo,
        transaction=transaction,
    )
