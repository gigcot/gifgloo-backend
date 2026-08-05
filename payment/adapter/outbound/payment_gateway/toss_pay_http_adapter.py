from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx

from payment.application.ports.outbound.payment_gateway.toss_pay_gateway import (
    CreateTossPayCheckoutCommand,
    CreateTossPayCheckoutResult,
    GetTossPayStatusCommand,
    GetTossPayStatusResult,
    TossPayGatewayPort,
)
from shared.exceptions import ExternalServiceException


class TossPayHttpAdapter(TossPayGatewayPort):
    def __init__(
        self,
        api_key: str,
        result_callback_url: str,
        return_url: str,
        cancel_url: str,
        base_url: str = "https://pay.toss.im/api/v2",
        timeout_seconds: float = 10.0,
    ):
        self._api_key = api_key
        self._result_callback_url = result_callback_url
        self._return_url = return_url
        self._cancel_url = cancel_url
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def create_checkout(
        self,
        command: CreateTossPayCheckoutCommand,
    ) -> CreateTossPayCheckoutResult:
        payload = await self._post(
            "/payments",
            {
                "apiKey": self._api_key,
                "orderNo": command.order_id,
                "amount": command.amount,
                "amountTaxFree": 0,
                "productDesc": command.product_description,
                "retUrl": self._return_url,
                "retCancelUrl": self._cancel_url,
                "autoExecute": True,
                "resultCallback": self._result_callback_url,
                "callbackVersion": "V2",
                "cashReceipt": True,
            },
        )
        return CreateTossPayCheckoutResult(
            pay_token=payload["payToken"],
            checkout_page=payload["checkoutPage"],
        )

    async def get_status(
        self,
        command: GetTossPayStatusCommand,
    ) -> GetTossPayStatusResult:
        payload = await self._post(
            "/status",
            {
                "apiKey": self._api_key,
                "orderNo": command.order_id,
            },
        )
        pay_transaction = next(
            (
                transaction
                for transaction in reversed(payload["transactions"])
                if transaction["stepType"] == "PAY"
            ),
            None,
        )
        paid_at = None
        transaction_id = None
        if payload["payStatus"] == "PAY_COMPLETE":
            if pay_transaction is None:
                raise ExternalServiceException("토스페이 결제 거래를 확인할 수 없습니다")
            paid_at = datetime.fromisoformat(payload["paidTs"].replace("Z", "+00:00"))
            if paid_at.tzinfo is None:
                paid_at = paid_at.replace(tzinfo=ZoneInfo("Asia/Seoul"))
            paid_at = paid_at.astimezone(timezone.utc)
            transaction_id = pay_transaction["transactionId"]

        return GetTossPayStatusResult(
            order_id=payload["orderNo"],
            pay_token=payload["payToken"],
            pay_status=payload["payStatus"],
            amount=payload["amount"],
            paid_at=paid_at,
            transaction_id=transaction_id,
        )

    async def _post(self, path: str, body: dict) -> dict:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.post(f"{self._base_url}{path}", json=body)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceException("토스페이 API 호출에 실패했습니다") from exc

        try:
            payload = response.json()
        except ValueError as exc:
            raise ExternalServiceException("토스페이 응답을 해석할 수 없습니다") from exc
        if payload["code"] != 0:
            raise ExternalServiceException(f"토스페이 요청 실패: {payload['msg']}")
        return payload
