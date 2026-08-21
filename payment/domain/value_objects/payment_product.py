from dataclasses import dataclass

from payment.domain.value_objects.payment_purpose import PaymentPurpose
from shared.exceptions import BusinessRuleException


@dataclass(frozen=True)
class PaymentProduct:
    id: str
    name: str
    amount: int
    purpose: PaymentPurpose
    credit_amount: int
    usage_count: int
    validity_days: int
    currency: str = "KRW"
    available: bool = True


PAYMENT_PRODUCTS = {
    "composition_pass_5_7d": PaymentProduct(
        id="composition_pass_5_7d",
        name="GIF 합성 5회 이용권",
        amount=6600,
        purpose=PaymentPurpose.COMPOSITION_PASS_PURCHASE,
        credit_amount=50,
        usage_count=5,
        validity_days=7,
    ),
}


def get_payment_product(product_id: str) -> PaymentProduct:
    try:
        product = PAYMENT_PRODUCTS[product_id]
    except KeyError:
        raise BusinessRuleException("판매 중인 결제 상품이 아닙니다")
    if not product.available:
        raise BusinessRuleException("판매 중인 결제 상품이 아닙니다")
    return product
