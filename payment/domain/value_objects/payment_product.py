from dataclasses import dataclass

from shared.exceptions import BusinessRuleException


@dataclass(frozen=True)
class PaymentProduct:
    id: str
    name: str
    amount: int
    credit_amount: int
    currency: str = "KRW"


PAYMENT_PRODUCTS = {
    "credits_50": PaymentProduct(
        id="credits_50",
        name="Gifgloo 크레딧 50개",
        amount=6600,
        credit_amount=50,
    ),
}


def get_payment_product(product_id: str) -> PaymentProduct:
    try:
        return PAYMENT_PRODUCTS[product_id]
    except KeyError:
        raise BusinessRuleException("판매 중인 결제 상품이 아닙니다")
