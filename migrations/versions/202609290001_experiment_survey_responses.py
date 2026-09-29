"""Add experiment survey responses."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202609290001"
down_revision = "202609240001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "experiment_survey_responses",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("experiment_code", sa.String(length=100), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column(
            "answers",
            sa.JSON().with_variant(postgresql.JSONB(), "postgresql"),
            nullable=False,
        ),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "experiment_code",
            "user_id",
            name="uq_experiment_survey_responses_experiment_user",
        ),
    )


def downgrade():
    op.drop_table("experiment_survey_responses")
