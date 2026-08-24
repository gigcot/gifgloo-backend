import os
from datetime import datetime

import jwt
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from credit_account.application.ports.inbound.charge import ChargeCreditCommand
from credit_account.application.ports.inbound.deduct import DeductCreditCommand
from credit_account.application.ports.inbound.get_balance import GetCreditBalanceCommand
from credit_account.application.ports.inbound.get_history import GetCreditHistoryCommand
from credit_account.application.services.charge_credit_service import ChargeCreditService
from credit_account.application.services.deduct_credit_service import DeductCreditService
from credit_account.application.services.get_credit_balance_service import GetCreditBalanceService
from credit_account.application.services.get_credit_history_service import GetCreditHistoryService
from credit_account.application.services.get_credit_lot_history_service import (
    GetCreditLotHistoryService,
)
from config.credit import (
    get_credit_balance_service,
    get_credit_history_service,
    get_credit_lot_history_service,
)
from credit_account.application.ports.inbound.get_lot_history import (
    GetCreditLotHistoryCommand,
)
from credit_account.domain.aggregates.credit_account import CreditAccount
from credit_account.domain.value_objects.transaction_type import TransactionType
from shared.pagination_cursor import decode_page_cursor, encode_page_cursor
from shared.session_token import decode_session_token

router = APIRouter(prefix="/credits", tags=["credits"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _get_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if not token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        payload = decode_session_token(token, SECRET_KEY)
        return payload["user_id"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(401, "유효하지 않은 토큰입니다")


def _next_cursor(created_at: datetime | None, item_id: str | None) -> str | None:
    if created_at is None or item_id is None:
        return None
    return encode_page_cursor(created_at, item_id)

# TODO: charge, deduct — DI 연결 후 활성화
# @router.post("/charge")
# @router.post("/deduct")

@router.get("/balance")
async def get_credit_balance(
    request: Request,
    service: GetCreditBalanceService = Depends(get_credit_balance_service),
):
    user_id = _get_user_id(request)
    result = await service.execute(GetCreditBalanceCommand(user_id))
    return {
        "balance": result.balance,
        "remaining_uses": result.remaining_uses,
        "nearest_expires_at": result.nearest_expires_at,
    }

@router.get("/lots")
async def get_credit_lot_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=256),
    service: GetCreditLotHistoryService = Depends(get_credit_lot_history_service),
):
    page_cursor = decode_page_cursor(cursor) if cursor else None
    result = await service.execute(
        GetCreditLotHistoryCommand(
            user_id=_get_user_id(request),
            limit=limit,
            cursor_created_at=page_cursor.created_at if page_cursor else None,
            cursor_id=page_cursor.item_id if page_cursor else None,
        )
    )
    return {
        "items": [
            {
                "lot_id": item.lot_id,
                "payment_id": item.payment_id,
                "granted_amount": item.granted_amount,
                "granted_uses": item.granted_uses,
                "remaining_amount": item.remaining_amount,
                "remaining_uses": item.remaining_uses,
                "expires_at": item.expires_at,
                "expired": item.expired,
                "created_at": item.created_at,
                "order_id": item.order_id,
                "payment_amount": item.payment_amount,
                "currency": item.currency,
                "purpose": item.purpose,
                "payment_status": item.payment_status,
                "approved_at": item.approved_at,
                "canceled_at": item.canceled_at,
            }
            for item in result.items
        ],
        "has_more": result.has_more,
        "next_cursor": _next_cursor(
            result.next_cursor_created_at,
            result.next_cursor_id,
        ),
    }


@router.get("/history")
async def get_credit_history(
    request: Request,
    limit: int = Query(default=20, ge=1, le=50),
    cursor: str | None = Query(default=None, max_length=256),
    service: GetCreditHistoryService = Depends(get_credit_history_service),
):
    page_cursor = decode_page_cursor(cursor) if cursor else None
    result = await service.execute(
        GetCreditHistoryCommand(
            user_id=_get_user_id(request),
            limit=limit,
            cursor_created_at=page_cursor.created_at if page_cursor else None,
            cursor_id=page_cursor.item_id if page_cursor else None,
        )
    )
    positive_types = {TransactionType.CHARGE, TransactionType.REFUND}
    return {
        "items": [
            {
                "transaction_id": transaction.id,
                "transaction_type": transaction.transaction_type.value,
                "amount": transaction.amount,
                "signed_amount": (
                    transaction.amount
                    if transaction.transaction_type in positive_types
                    else -transaction.amount
                ),
                "uses": transaction.amount // CreditAccount.composition_cost,
                "source_type": (
                    transaction.source_type.value
                    if transaction.source_type is not None
                    else None
                ),
                "source_id": transaction.source_id,
                "credit_lot_id": transaction.credit_lot_id,
                "reason": transaction.reason,
                "balance_after": transaction.balance_after,
                "balance_after_uses": (
                    transaction.balance_after // CreditAccount.composition_cost
                    if transaction.balance_after is not None
                    else None
                ),
                "created_at": transaction.created_at,
            }
            for transaction in result.transactions
        ],
        "has_more": result.has_more,
        "next_cursor": _next_cursor(
            result.next_cursor_created_at,
            result.next_cursor_id,
        ),
    }
