"""payment environment

Revision ID: 202608170001
Revises: 202608090002
Create Date: 2026-08-17
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202608170001"
down_revision: Union[str, None] = "202608090002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "payment_environment",
            sa.String(),
            nullable=False,
            server_default="UNKNOWN",
        ),
    )
    op.alter_column("payments", "payment_environment", server_default=None)


def downgrade() -> None:
    op.drop_column("payments", "payment_environment")
