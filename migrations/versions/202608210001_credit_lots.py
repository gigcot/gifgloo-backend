"""credit lots

Revision ID: 202608210001
Revises: 202608190001
Create Date: 2026-08-21
"""

from collections.abc import Sequence
from datetime import datetime, timedelta, timezone
import uuid

import sqlalchemy as sa
from alembic import op

revision: str = "202608210001"
down_revision: str | None = "202608190001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "credit_lots",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("account_user_id", sa.String(), nullable=False),
        sa.Column("source_type", sa.String(), nullable=True),
        sa.Column("source_id", sa.String(), nullable=True),
        sa.Column("granted_amount", sa.Integer(), nullable=False),
        sa.Column("remaining_amount", sa.Integer(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["account_user_id"], ["credit_accounts.user_id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_type",
            "source_id",
            name="uq_credit_lots_source",
        ),
    )
    op.create_index(
        "ix_credit_lots_account_expiration",
        "credit_lots",
        ["account_user_id", "expires_at"],
        unique=False,
    )
    op.add_column(
        "credit_transactions",
        sa.Column("credit_lot_id", sa.String(), nullable=True),
    )
    op.create_foreign_key(
        "fk_credit_transactions_credit_lot_id",
        "credit_transactions",
        "credit_lots",
        ["credit_lot_id"],
        ["id"],
    )

    accounts = sa.table(
        "credit_accounts",
        sa.column("user_id", sa.String()),
        sa.column("balance", sa.Integer()),
    )
    rows = op.get_bind().execute(
        sa.select(accounts.c.user_id, accounts.c.balance).where(accounts.c.balance > 0)
    ).all()
    if rows:
        granted_at = datetime.now(timezone.utc)
        expires_at = granted_at + timedelta(days=7)
        lots = sa.table(
            "credit_lots",
            sa.column("id", sa.String()),
            sa.column("account_user_id", sa.String()),
            sa.column("source_type", sa.String()),
            sa.column("source_id", sa.String()),
            sa.column("granted_amount", sa.Integer()),
            sa.column("remaining_amount", sa.Integer()),
            sa.column("expires_at", sa.DateTime(timezone=True)),
            sa.column("created_at", sa.DateTime(timezone=True)),
        )
        op.bulk_insert(
            lots,
            [
                {
                    "id": str(uuid.uuid4()),
                    "account_user_id": row.user_id,
                    "source_type": "ADMIN",
                    "source_id": f"legacy:{row.user_id}",
                    "granted_amount": row.balance,
                    "remaining_amount": row.balance,
                    "expires_at": expires_at,
                    "created_at": granted_at,
                }
                for row in rows
            ],
        )


def downgrade() -> None:
    op.drop_constraint(
        "fk_credit_transactions_credit_lot_id",
        "credit_transactions",
        type_="foreignkey",
    )
    op.drop_column("credit_transactions", "credit_lot_id")
    op.drop_index(
        "ix_credit_lots_account_expiration",
        table_name="credit_lots",
    )
    op.drop_table("credit_lots")
