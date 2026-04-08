import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from credit_account.application.ports.inbound.charge import ChargeCreditCommand
from credit_account.application.ports.inbound.deduct import DeductCreditCommand
from credit_account.application.ports.inbound.get_balance import GetCreditBalanceCommand
from credit_account.application.ports.inbound.get_history import GetCreditHistoryCommand
from credit_account.application.services.charge_credit_service import ChargeCreditService
from credit_account.application.services.deduct_credit_service import DeductCreditService
from credit_account.application.services.get_credit_balance_service import GetCreditBalanceService
from credit_account.application.services.get_credit_history_service import GetCreditHistoryService
from config.credit import get_credit_balance_service

router = APIRouter(prefix="/credits", tags=["credits"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


def _get_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if not token:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["user_id"]
    except Exception:
        raise HTTPException(401, "유효하지 않은 토큰입니다")

# TODO: charge, deduct — DI 연결 후 활성화
# @router.post("/charge")
# @router.post("/deduct")

@router.get("/balance")
def get_credit_balance(
    request: Request,
    service: GetCreditBalanceService = Depends(get_credit_balance_service),
):
    user_id = _get_user_id(request)
    result = service.execute(GetCreditBalanceCommand(user_id))
    return {"balance": result.balance}

# TODO: get_history — DI 연결 후 활성화
# @router.get("/history")
