"""composition feedback

Revision ID: 202609200001
Revises: 202609180001
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "202609200001"
down_revision: str | None = "202609180001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "composition_feedbacks",
        sa.Column("composition_job_id", sa.String(), nullable=False),
        sa.Column("satisfied", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["composition_job_id"],
            ["composition_jobs.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("composition_job_id"),
    )


def downgrade() -> None:
    op.drop_table("composition_feedbacks")
