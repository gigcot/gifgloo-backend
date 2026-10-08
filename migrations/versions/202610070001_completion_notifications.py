"""Store opt-in, per-composition Web Push deliveries."""
from alembic import op
import sqlalchemy as sa

revision = "202610070001"
down_revision = "202610050001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("composition_notifications",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("job_id", sa.String(), sa.ForeignKey("composition_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("endpoint_hash", sa.String(64), nullable=False),
        sa.Column("endpoint", sa.String(4096), nullable=False),
        sa.Column("p256dh", sa.String(128), nullable=False),
        sa.Column("auth", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("job_id", "endpoint_hash", name="uq_composition_notification_browser"),
    )
    op.create_index("ix_composition_notifications_ready", "composition_notifications", ["status", "next_attempt_at"])


def downgrade():
    op.drop_index("ix_composition_notifications_ready", table_name="composition_notifications")
    op.drop_table("composition_notifications")
