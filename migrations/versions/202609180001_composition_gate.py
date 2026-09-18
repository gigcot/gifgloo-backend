"""composition admission gate

Revision ID: 202609180001
Revises: 202608240001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609180001"
down_revision: str | None = "202608240001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    table = op.create_table(
        "composition_gate",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("active_job_id", sa.String(), nullable=True),
        sa.Column("active_run_id", sa.String(), nullable=True),
        sa.Column("lease_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_edit_sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.bulk_insert(table, [{"id": 1}])


def downgrade() -> None:
    op.drop_table("composition_gate")
