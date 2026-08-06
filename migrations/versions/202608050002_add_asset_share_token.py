"""add asset share token

Revision ID: 202608050002
Revises: 202608050001
Create Date: 2026-08-05
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202608050002"
down_revision: str | None = "202608050001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("assets", sa.Column("share_token", sa.String(), nullable=True))
    op.create_index("ix_assets_share_token", "assets", ["share_token"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_assets_share_token", table_name="assets")
    op.drop_column("assets", "share_token")
