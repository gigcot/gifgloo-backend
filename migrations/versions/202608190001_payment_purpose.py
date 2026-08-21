"""payment purpose

Revision ID: 202608190001
Revises: 202608170001
Create Date: 2026-08-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608190001"
down_revision: str | None = "202608170001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "payments",
        sa.Column(
            "purpose",
            sa.String(),
            nullable=False,
            server_default="CREDIT_TOP_UP",
        ),
    )
    op.alter_column("payments", "purpose", server_default=None)


def downgrade() -> None:
    op.drop_column("payments", "purpose")
