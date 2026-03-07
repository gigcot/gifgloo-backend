from fastapi import APIRouter, Depends
from pydantic import BaseModel

from credit_account.application.ports.inbound.charge import ChargeCreditCommand
from credit_account.application.ports.inbound.deduct import DeductCreditCommand
from credit_account.application.ports.inbound.get_balance import GetCreditBalanceCommand
from credit_account.application.ports.inbound.get_history import GetCreditHistoryCommand
from credit_account.application.services.charge_credit_service import ChargeCreditService
from credit_account.application.services.deduct_credit_service import DeductCreditService
from credit_account.application.services.get_credit_balance_service import GetCreditBalanceService
from credit_account.application.services.get_credit_history_service import GetCreditHistoryService

router = APIRouter(prefix="/credit_account", tags=["credit_account"])

SECRET_KEY = "TODO: config에서 주입"  # TODO: config로 분리

@router.post("/charge")
def charge_credit(
    amount: int,
    user_id: str = "",  # TODO: JWT에서 추출,
    service: ChargeCreditService = Depends(),
):
    service.execute(ChargeCreditCommand(user_id, amount))

@router.post("/deduct")
def deduct_credit(
    service: DeductCreditService = Depends(),
    user_id: str = "",  # TODO: JWT에서 추출,
):  
    service.execute(DeductCreditCommand(user_id))

@router.get("/get_balance")
def get_credit_balance(
    user_id: str = "",  # TODO: JWT에서 추출,
    service: GetCreditBalanceService = Depends()
):
    return service.execute(GetCreditBalanceCommand(user_id))

@router.get("/get_history")
def get_credit_history(
    user_id: str = "",  # TODO: JWT에서 추출,
    service: GetCreditHistoryService = Depends(),
):
    return service.execute(GetCreditHistoryCommand(user_id))
