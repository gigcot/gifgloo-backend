"""payment processing

Revision ID: 202608050001
Revises: 202607310001
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608050001"
down_revision: str | None = "202607310001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "payments",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column("currency", sa.String(), nullable=False),
        sa.Column("credit_amount", sa.Integer(), nullable=False),
        sa.Column("provider_payment_id", sa.String(), nullable=True),
        sa.Column("provider_transaction_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("failed_reason", sa.String(), nullable=True),
        sa.Column("cancel_reason", sa.String(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("canceled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("credit_granted_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("order_id", name="uq_payments_order_id"),
        sa.UniqueConstraint(
            "provider",
            "provider_payment_id",
            name="uq_payments_provider_payment_id_by_provider",
        ),
    )
    op.create_index("ix_payments_user_id", "payments", ["user_id"], unique=False)

    op.create_table(
        "payment_inbox",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("provider", sa.String(), nullable=False),
        sa.Column("external_event_id", sa.String(), nullable=False),
        sa.Column("event_type", sa.String(), nullable=False),
        sa.Column("order_id", sa.String(), nullable=False),
        sa.Column("payment_id", sa.String(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "provider",
            "external_event_id",
            name="uq_payment_inbox_provider_event",
        ),
    )
    op.create_index(
        "ix_payment_inbox_status",
        "payment_inbox",
        ["status"],
        unique=False,
    )

    op.add_column(
        "credit_transactions",
        sa.Column("source_type", sa.String(), nullable=True),
    )
    op.add_column(
        "credit_transactions",
        sa.Column("source_id", sa.String(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_credit_transactions_source",
        "credit_transactions",
        ["source_type", "source_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_credit_transactions_source",
        "credit_transactions",
        type_="unique",
    )
    op.drop_column("credit_transactions", "source_id")
    op.drop_column("credit_transactions", "source_type")

    op.drop_index("ix_payment_inbox_status", table_name="payment_inbox")
    op.drop_table("payment_inbox")
    op.drop_index("ix_payments_user_id", table_name="payments")
    op.drop_table("payments")
