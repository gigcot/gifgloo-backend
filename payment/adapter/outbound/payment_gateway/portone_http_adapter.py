from datetime import datetime, timezone
from urllib.parse import quote

import httpx

from payment.application.ports.outbound.payment_gateway.portone_gateway import (
    GetPortOnePaymentCommand,
    GetPortOnePaymentResult,
    PortOneGatewayPort,
)
from payment.domain.value_objects.payment_environment import PaymentEnvironment
from shared.exceptions import ExternalServiceException


class PortOneHttpAdapter(PortOneGatewayPort):
    def __init__(
        self,
        api_secret: str,
        base_url: str = "https://api.portone.io",
        timeout_seconds: float = 10.0,
    ):
        self._api_secret = api_secret
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def get_payment(
        self,
        command: GetPortOnePaymentCommand,
    ) -> GetPortOnePaymentResult:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as client:
                response = await client.get(
                    f"{self._base_url}/payments/{quote(command.payment_id, safe='')}",
                    headers={"Authorization": f"PortOne {self._api_secret}"},
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise ExternalServiceException("포트원 결제 조회에 실패했습니다") from exc

        try:
            payload = response.json()
            paid_at = datetime.fromisoformat(payload["paidAt"].replace("Z", "+00:00"))
            if paid_at.tzinfo is None:
                raise ValueError("paidAt timezone is required")
            channel = payload["channel"]
            channel_type = channel["type"]
            if channel_type not in (
                PaymentEnvironment.TEST.value,
                PaymentEnvironment.LIVE.value,
            ):
                raise ValueError("unsupported PortOne channel type")
            result = GetPortOnePaymentResult(
                payment_id=payload["id"],
                transaction_id=payload["transactionId"],
                status=payload["status"],
                amount=payload["amount"]["total"],
                currency=payload["currency"],
                paid_at=paid_at.astimezone(timezone.utc),
                pg_provider=channel["pgProvider"],
                payment_environment=PaymentEnvironment(channel_type),
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise ExternalServiceException("포트원 결제 응답을 해석할 수 없습니다") from exc

        return result
