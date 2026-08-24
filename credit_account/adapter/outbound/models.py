from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import relationship

from config.database import Base


class CreditAccountModel(Base):
    __tablename__ = "credit_accounts"

    user_id = Column(String, primary_key=True)
    balance = Column(Integer, nullable=False, default=0)

    transactions = relationship("CreditTransactionModel", back_populates="account", cascade="all, delete-orphan")
    lots = relationship("CreditLotModel", back_populates="account", cascade="all, delete-orphan")


class CreditLotModel(Base):
    __tablename__ = "credit_lots"
    __table_args__ = (
        UniqueConstraint(
            "source_type",
            "source_id",
            name="uq_credit_lots_source",
        ),
        Index("ix_credit_lots_account_expiration", "account_user_id", "expires_at"),
        Index(
            "ix_credit_lots_user_payment_history",
            "account_user_id",
            "source_type",
            "created_at",
            "id",
        ),
    )

    id = Column(String, primary_key=True)
    account_user_id = Column(String, ForeignKey("credit_accounts.user_id"), nullable=False)
    source_type = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    granted_amount = Column(Integer, nullable=False)
    remaining_amount = Column(Integer, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    account = relationship("CreditAccountModel", back_populates="lots")


class CreditTransactionModel(Base):
    __tablename__ = "credit_transactions"
    __table_args__ = (
        UniqueConstraint(
            "transaction_type",
            "source_type",
            "source_id",
            name="uq_credit_transactions_type_source",
        ),
        Index("ix_credit_transactions_source", "source_type", "source_id"),
        Index(
            "ix_credit_transactions_user_history",
            "account_user_id",
            "created_at",
            "id",
            postgresql_where=text(
                "transaction_type IN ('CHARGE', 'DEDUCT', 'REFUND')"
            ),
        ),
    )

    id = Column(String, primary_key=True)
    account_user_id = Column(String, ForeignKey("credit_accounts.user_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    source_type = Column(String, nullable=True)
    source_id = Column(String, nullable=True)
    credit_lot_id = Column(String, ForeignKey("credit_lots.id"), nullable=True)
    reason = Column(String, nullable=True)
    balance_after = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False)

    account = relationship("CreditAccountModel", back_populates="transactions")
