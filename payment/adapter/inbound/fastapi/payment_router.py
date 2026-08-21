import os

import jwt
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from config.payment import (
    get_confirm_portone_payment_service,
    get_create_payment_order_service,
    get_handle_toss_pay_callback_service,
)
from payment.application.ports.inbound.confirm_portone_payment import (
    ConfirmPortOnePaymentCommand,
)
from payment.application.ports.inbound.create_payment_order import (
    CreatePaymentOrderCommand,
)
from payment.application.ports.inbound.handle_toss_pay_callback import (
    HandleTossPayCallbackCommand,
)
from payment.application.services.create_payment_order_service import (
    CreatePaymentOrderService,
)
from payment.application.services.confirm_portone_payment_service import (
    ConfirmPortOnePaymentService,
)
from payment.application.services.handle_toss_pay_callback_service import (
    HandleTossPayCallbackService,
)
from payment.domain.value_objects.payment_product import PAYMENT_PRODUCTS
from shared.session_token import decode_session_token

router = APIRouter(prefix="/payments", tags=["payments"])

SECRET_KEY = os.getenv("JWT_SECRET_KEY")


class CreatePaymentCheckoutBody(BaseModel):
    product_id: str = Field(min_length=1, max_length=64)


class ConfirmPortOnePaymentBody(BaseModel):
    payment_id: str = Field(min_length=1, max_length=64)


class PortOneWebhookData(BaseModel):
    payment_id: str = Field(alias="paymentId", min_length=1, max_length=64)


class PortOneWebhookBody(BaseModel):
    type: str
    data: PortOneWebhookData


class TossPayCallbackBody(BaseModel):
    status: str = Field(min_length=1, max_length=20)
    pay_token: str = Field(alias="payToken", min_length=1, max_length=30)
    order_id: str = Field(
        alias="orderNo",
        pattern=r"^gifgloo_[0-9a-f]{32}$",
        max_length=50,
    )
    pay_method: str = Field(alias="payMethod", min_length=1, max_length=10)
    amount: int = Field(ge=1, le=1_000_000_000)
    discounted_amount: int = Field(alias="discountedAmount", ge=0)
    paid_amount: int = Field(alias="paidAmount", ge=0)
    paid_at: str = Field(alias="paidTs", min_length=1, max_length=20)
    transaction_id: str = Field(
        alias="transactionId",
        min_length=1,
        max_length=36,
    )


def _get_user_id(request: Request) -> str:
    token = request.cookies.get("user_token")
    if token is None:
        raise HTTPException(401, "인증이 필요합니다")
    try:
        payload = decode_session_token(token, SECRET_KEY)
        return payload["user_id"]
    except (jwt.PyJWTError, KeyError):
        raise HTTPException(401, "유효하지 않은 토큰입니다")


@router.get("/products")
async def list_payment_products():
    return [
        {
            "id": product.id,
            "name": product.name,
            "amount": product.amount,
            "credit_amount": product.credit_amount,
            "purpose": product.purpose.value,
            "usage_count": product.usage_count,
            "validity_days": product.validity_days,
            "currency": product.currency,
        }
        for product in PAYMENT_PRODUCTS.values()
        if product.available
    ]


@router.post("/checkout")
async def create_payment_checkout(
    body: CreatePaymentCheckoutBody,
    request: Request,
    service: CreatePaymentOrderService = Depends(get_create_payment_order_service),
):
    result = await service.execute(
        CreatePaymentOrderCommand(
            user_id=_get_user_id(request),
            product_id=body.product_id,
        )
    )
    return {
        "payment_id": result.payment_id,
        "order_id": result.order_id,
        "amount": result.amount,
        "credit_amount": result.credit_amount,
        "purpose": result.purpose.value,
        "currency": result.currency,
        "status": result.status,
        "order_name": result.order_name,
    }


@router.post("/complete")
async def confirm_portone_payment(
    body: ConfirmPortOnePaymentBody,
    request: Request,
    service: ConfirmPortOnePaymentService = Depends(
        get_confirm_portone_payment_service
    ),
):
    result = await service.execute(
        ConfirmPortOnePaymentCommand(
            payment_id=body.payment_id,
            expected_user_id=_get_user_id(request),
        )
    )
    return {
        "ok": True,
        "payment_id": result.payment_id,
        "status": result.status,
        "already_processed": result.already_processed,
        "test_payment": result.test_payment,
    }


@router.post("/portone/webhook")
async def handle_portone_webhook(
    body: PortOneWebhookBody,
    service: ConfirmPortOnePaymentService = Depends(
        get_confirm_portone_payment_service
    ),
):
    if body.type != "Transaction.Paid":
        return {"ok": True, "ignored": True}

    result = await service.execute(
        ConfirmPortOnePaymentCommand(
            payment_id=body.data.payment_id,
            expected_user_id=None,
        )
    )
    return {
        "ok": True,
        "payment_id": result.payment_id,
        "already_processed": result.already_processed,
        "test_payment": result.test_payment,
    }


@router.post("/toss/callback")
async def handle_toss_pay_callback(
    body: TossPayCallbackBody,
    service: HandleTossPayCallbackService = Depends(
        get_handle_toss_pay_callback_service
    ),
):
    payload = body.model_dump(by_alias=True)
    result = await service.execute(
        HandleTossPayCallbackCommand(
            status=body.status,
            pay_token=body.pay_token,
            order_id=body.order_id,
            transaction_id=body.transaction_id,
            payload=payload,
        )
    )
    return {
        "ok": True,
        "payment_id": result.payment_id,
        "status": result.status,
        "already_processed": result.already_processed,
    }
