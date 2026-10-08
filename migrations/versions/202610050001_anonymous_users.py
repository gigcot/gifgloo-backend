"""Support anonymous users and invalidate pre-upgrade sessions."""

from alembic import op
import sqlalchemy as sa

revision = "202610050001"
down_revision = "202609290001"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("users", "provider", nullable=True)
    op.alter_column("users", "provider_id", nullable=True)
    op.add_column("users", sa.Column("session_version", sa.Integer(), nullable=False, server_default="0"))
    op.create_unique_constraint("uq_users_social_account", "users", ["provider", "provider_id"])
    op.create_check_constraint("ck_users_social_pair", "users", "(provider IS NULL) = (provider_id IS NULL)")


def downgrade():
    # Anonymous rows must be deliberately migrated before restoring NOT NULL.
    op.alter_column("users", "provider", nullable=False)
    op.alter_column("users", "provider_id", nullable=False)
    op.drop_constraint("ck_users_social_pair", "users", type_="check")
    op.drop_constraint("uq_users_social_account", "users", type_="unique")
    op.drop_column("users", "session_version")
