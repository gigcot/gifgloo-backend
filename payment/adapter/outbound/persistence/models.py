from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint

from config.database import Base


class PaymentModel(Base):
    __tablename__ = "payments"
    __table_args__ = (
        UniqueConstraint("order_id", name="uq_payments_order_id"),
        UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_payments_provider_payment_id_by_provider",
        ),
    )

    id = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    provider = Column(String, nullable=False)
    order_id = Column(String, nullable=False)
    amount = Column(Integer, nullable=False)
    currency = Column(String, nullable=False)
    credit_amount = Column(Integer, nullable=False)
    provider_payment_id = Column(String, nullable=True)
    provider_transaction_id = Column(String, nullable=True)
    status = Column(String, nullable=False)
    failed_reason = Column(String, nullable=True)
    cancel_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False)
    authorized_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    credit_granted_at = Column(DateTime(timezone=True), nullable=True)


class PaymentInboxModel(Base):
    __tablename__ = "payment_inbox"
    __table_args__ = (
        UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_payment_inbox_provider_event",
        ),
    )

    id = Column(String, primary_key=True)
    provider = Column(String, nullable=False)
    external_event_id = Column(String, nullable=False)
    event_type = Column(String, nullable=False)
    order_id = Column(String, nullable=False)
    payment_id = Column(String, ForeignKey("payments.id"), nullable=True)
    payload = Column(JSON, nullable=False)
    status = Column(String, nullable=False)
    attempts = Column(Integer, nullable=False)
    received_at = Column(DateTime(timezone=True), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
