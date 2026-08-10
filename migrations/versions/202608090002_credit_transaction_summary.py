"""credit transaction summary

Revision ID: 202608090002
Revises: 202608090001
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202608090002"
down_revision: Union[str, None] = "202608090001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    constraint_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("credit_transactions")
    }
    index_names = {
        index["name"]
        for index in inspector.get_indexes("credit_transactions")
    }
    if "uq_credit_transactions_source" in constraint_names:
        op.drop_constraint(
            "uq_credit_transactions_source",
            "credit_transactions",
            type_="unique",
        )
    elif "uq_credit_transactions_source" in index_names:
        op.drop_index(
            "uq_credit_transactions_source",
            table_name="credit_transactions",
        )
    op.add_column(
        "credit_transactions",
        sa.Column("balance_after", sa.Integer(), nullable=True),
    )
    op.create_unique_constraint(
        "uq_credit_transactions_type_source",
        "credit_transactions",
        ["transaction_type", "source_type", "source_id"],
    )
    op.create_index(
        "ix_credit_transactions_source",
        "credit_transactions",
        ["source_type", "source_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_credit_transactions_source", table_name="credit_transactions")
    op.drop_constraint(
        "uq_credit_transactions_type_source",
        "credit_transactions",
        type_="unique",
    )
    op.drop_column("credit_transactions", "balance_after")
    op.create_unique_constraint(
        "uq_credit_transactions_source",
        "credit_transactions",
        ["source_type", "source_id"],
    )
