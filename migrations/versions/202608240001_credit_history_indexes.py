"""credit history indexes

Revision ID: 202608240001
Revises: 202608210001
Create Date: 2026-08-24
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608240001"
down_revision: str | None = "202608210001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.get_context().autocommit_block():
        op.create_index(
            "ix_credit_lots_user_payment_history",
            "credit_lots",
            ["account_user_id", "source_type", "created_at", "id"],
            unique=False,
            if_not_exists=True,
            postgresql_concurrently=True,
        )
        op.create_index(
            "ix_credit_transactions_user_history",
            "credit_transactions",
            ["account_user_id", "created_at", "id"],
            unique=False,
            if_not_exists=True,
            postgresql_concurrently=True,
            postgresql_where=sa.text(
                "transaction_type IN ('CHARGE', 'DEDUCT', 'REFUND')"
            ),
        )


def downgrade() -> None:
    with op.get_context().autocommit_block():
        op.drop_index(
            "ix_credit_transactions_user_history",
            table_name="credit_transactions",
            if_exists=True,
            postgresql_concurrently=True,
        )
        op.drop_index(
            "ix_credit_lots_user_payment_history",
            table_name="credit_lots",
            if_exists=True,
            postgresql_concurrently=True,
        )
