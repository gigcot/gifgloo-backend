from sqlalchemy import Column, String, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from config.database import Base


class CreditAccountModel(Base):
    __tablename__ = "credit_accounts"

    user_id = Column(String, primary_key=True)
    balance = Column(Integer, nullable=False, default=0)

    transactions = relationship("CreditTransactionModel", back_populates="account", cascade="all, delete-orphan")


class CreditTransactionModel(Base):
    __tablename__ = "credit_transactions"

    id = Column(String, primary_key=True)
    account_user_id = Column(String, ForeignKey("credit_accounts.user_id"), nullable=False)
    amount = Column(Integer, nullable=False)
    transaction_type = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), nullable=False)

    account = relationship("CreditAccountModel", back_populates="transactions")
