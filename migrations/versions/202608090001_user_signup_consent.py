"""user signup consent

Revision ID: 202608090001
Revises: 202608060001
Create Date: 2026-08-09
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "202608090001"
down_revision: Union[str, None] = "202608060001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("users", sa.Column("terms_version", sa.String(), nullable=True))
    op.add_column("users", sa.Column("privacy_version", sa.String(), nullable=True))
    op.add_column(
        "users",
        sa.Column(
            "is_fourteen_or_older",
            sa.Boolean(),
            nullable=False,
            server_default=sa.false(),
        ),
    )
    op.add_column(
        "users",
        sa.Column("consented_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.alter_column("users", "is_fourteen_or_older", server_default=None)


def downgrade() -> None:
    op.drop_column("users", "consented_at")
    op.drop_column("users", "is_fourteen_or_older")
    op.drop_column("users", "privacy_version")
    op.drop_column("users", "terms_version")
